# ========================================================================== #
#                                                                            #
#    KVMD - The main PiKVM daemon.                                           #
#                                                                            #
#    Copyright (C) 2020  Maxim Devaev <mdevaev@gmail.com>                    #
#                                                                            #
#    This program is free software: you can redistribute it and/or modify    #
#    it under the terms of the GNU General Public License as published by    #
#    the Free Software Foundation, either version 3 of the License, or       #
#    (at your option) any later version.                                     #
#                                                                            #
#    This program is distributed in the hope that it will be useful,         #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of          #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           #
#    GNU General Public License for more details.                            #
#                                                                            #
#    You should have received a copy of the GNU General Public License       #
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.  #
#                                                                            #
# ========================================================================== #


import types

from typing import AsyncGenerator

import aiohttp

try:
    import ustreamer
except ImportError:
    ustreamer = None

from .. import tools
from .. import aiotools
from .. import htclient


# =====
class StreamerError(Exception):
    pass


class StreamerTempError(StreamerError):
    pass


class StreamerPermError(StreamerError):
    pass


# =====
class StreamFormats:
    JPEG = 1195724874    # V4L2_PIX_FMT_JPEG
    H264 = 875967048     # V4L2_PIX_FMT_H264
    _MJPEG = 1196444237  # V4L2_PIX_FMT_MJPEG


class BaseStreamerClient:
    def get_format(self) -> int:
        raise NotImplementedError()

    async def read_stream(self) -> AsyncGenerator[dict, None]:
        if self is not None:  # XXX: Vulture and pylint hack
            raise NotImplementedError()
        yield


class HttpStreamerClient(BaseStreamerClient):
    def __init__(
        self,
        name: str,
        unix_path: str,
        timeout: float,
        user_agent: str,
    ) -> None:

        self.__name = name
        self.__unix_path = unix_path
        self.__timeout = timeout
        self.__user_agent = user_agent

    def get_format(self) -> int:
        return StreamFormats.JPEG

    async def read_stream(self) -> AsyncGenerator[dict, None]:
        try:
            async with self.__make_http_session() as session:
                async with session.get(
                    url=self.__make_url("stream"),
                    params={"extra_headers": "1"},
                ) as response:
                    htclient.raise_not_200(response)
                    reader = aiohttp.MultipartReader.from_response(response)
                    self.__patch_stream_reader(reader.resp.content)

                    while True:
                        frame = await reader.next()  # pylint: disable=not-callable
                        if not isinstance(frame, aiohttp.BodyPartReader):
                            raise StreamerTempError("Expected body part")

                        data = bytes(await frame.read())
                        if not data:
                            break

                        yield {
                            "online": (frame.headers["X-UStreamer-Online"] == "true"),
                            "width": int(frame.headers["X-UStreamer-Width"]),
                            "height": int(frame.headers["X-UStreamer-Height"]),
                            "data": data,
                            "format": StreamFormats.JPEG,
                        }
        except Exception as err:  # Тут бывают и ассерты, и KeyError, и прочая херня
            if isinstance(err, StreamerTempError):
                raise
            raise StreamerTempError(tools.efmt(err))
        raise StreamerTempError("Reached EOF")

    def __make_http_session(self) -> aiohttp.ClientSession:
        kwargs: dict = {
            "headers": {"User-Agent": self.__user_agent},
            "connector": aiohttp.UnixConnector(path=self.__unix_path),
            "timeout": aiohttp.ClientTimeout(
                connect=self.__timeout,
                sock_read=self.__timeout,
            ),
        }
        return aiohttp.ClientSession(**kwargs)

    def __make_url(self, handle: str) -> str:
        assert not handle.startswith("/"), handle
        return f"http://localhost:0/{handle}"

    def __patch_stream_reader(self, reader: aiohttp.StreamReader) -> None:
        # https://github.com/pikvm/pikvm/issues/92
        # Infinite looping in BodyPartReader.read() because _at_eof flag.

        orig_read = reader.read

        async def read(self: aiohttp.StreamReader, n: int=-1) -> bytes:  # pylint: disable=invalid-name
            if self.is_eof():
                raise StreamerTempError("StreamReader.read(): Reached EOF")
            return (await orig_read(n))

        reader.read = types.MethodType(read, reader)  # type: ignore

    def __str__(self) -> str:
        return f"HttpStreamerClient({self.__name})"


class MemsinkStreamerClient(BaseStreamerClient):
    def __init__(
        self,
        name: str,
        fmt: int,
        obj: str,
        lock_timeout: float,
        wait_timeout: float,
        drop_same_frames: float,
    ) -> None:

        self.__name = name
        self.__fmt = fmt
        self.__kwargs: dict = {
            "obj": obj,
            "lock_timeout": lock_timeout,
            "wait_timeout": wait_timeout,
            "drop_same_frames": drop_same_frames,
        }

    def get_format(self) -> int:
        return self.__fmt

    async def read_stream(self) -> AsyncGenerator[dict, None]:
        if ustreamer is None:
            raise StreamerPermError("Missing ustreamer library")
        try:
            with ustreamer.Memsink(**self.__kwargs) as sink:
                while True:
                    frame = await aiotools.run_async(sink.wait_frame)
                    if frame is not None:
                        self.__check_format(frame["format"])
                        yield frame
        except StreamerPermError:
            raise
        except FileNotFoundError as err:
            raise StreamerTempError(tools.efmt(err))
        except Exception as err:
            raise StreamerPermError(tools.efmt(err))

    def __check_format(self, fmt: int) -> None:
        if fmt == StreamFormats._MJPEG:  # pylint: disable=protected-access
            fmt = StreamFormats.JPEG
        if fmt != self.__fmt:
            raise StreamerPermError("Invalid sink format")

    def __str__(self) -> str:
        return f"MemsinkStreamerClient({self.__name})"
