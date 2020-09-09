# ========================================================================== #
#                                                                            #
#    KVMD - The main Pi-KVM daemon.                                          #
#                                                                            #
#    Copyright (C) 2018  Maxim Devaev <mdevaev@gmail.com>                    #
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


from typing import List
from typing import Set
from typing import Optional
from typing import Any

from ..keyboard.mappings import KEYMAP

from . import raise_error
from . import check_string_in_list
from . import check_re_match
from . import check_len

from .basic import valid_stripped_string_not_empty
from .basic import valid_number
from .basic import valid_string_list

from .os import valid_printable_filename


# =====
def valid_atx_power_action(arg: Any) -> str:
    return check_string_in_list(arg, "ATX power action", ["on", "off", "off_hard", "reset_hard"])


def valid_atx_button(arg: Any) -> str:
    return check_string_in_list(arg, "ATX button", ["power", "power_long", "reset"])


def valid_msd_image_name(arg: Any) -> str:
    return valid_printable_filename(arg, name="MSD image name")  # pragma: nocover


def valid_info_fields(arg: Any, variants: Set[str]) -> Set[str]:
    return set(valid_string_list(
        arg=str(arg).strip(),
        subval=(lambda field: check_string_in_list(field, "info field", variants)),
        name="info fields list",
    ))


def valid_log_seek(arg: Any) -> int:
    return int(valid_number(arg, min=0, name="log seek"))


def valid_stream_quality(arg: Any) -> int:
    return int(valid_number(arg, min=1, max=100, name="stream quality"))


def valid_stream_fps(arg: Any) -> int:
    return int(valid_number(arg, min=0, max=120, name="stream FPS"))


def valid_stream_resolution(arg: Any) -> str:
    name = "stream resolution"
    arg = valid_stripped_string_not_empty(arg, name)
    parts = arg.split("x")
    if len(parts) != 2:
        raise_error(arg, name)
    width = int(valid_number(parts[0], min=1, name=f"{name} (width)"))
    height = int(valid_number(parts[1], min=1, name=f"{name} (height)"))
    return f"{width}x{height}"


# =====
def valid_hid_key(arg: Any) -> str:
    return check_string_in_list(arg, "HID key", KEYMAP, lower=False)


def valid_hid_mouse_move(arg: Any) -> int:
    arg = valid_number(arg, name="HID mouse move")
    return min(max(-32768, arg), 32767)


def valid_hid_mouse_button(arg: Any) -> str:
    return check_string_in_list(arg, "HID mouse button", ["left", "right", "middle", "up", "down"])


def valid_hid_mouse_wheel(arg: Any) -> int:
    arg = valid_number(arg, name="HID mouse wheel")
    return min(max(-127, arg), 127)


# =====
def valid_ugpio_driver(arg: Any, variants: Optional[Set[str]]=None) -> str:
    name = "GPIO driver"
    arg = check_len(check_re_match(arg, name, r"^[a-zA-Z_][a-zA-Z0-9_-]*$"), name, 255)
    if variants is not None:
        arg = check_string_in_list(arg, f"configured {name}", variants, False)
    return arg


def valid_ugpio_channel(arg: Any) -> str:
    name = "GPIO channel"
    return check_len(check_re_match(arg, name, r"^[a-zA-Z_][a-zA-Z0-9_-]*$"), name, 255)


def valid_ugpio_mode(arg: Any) -> str:
    return check_string_in_list(arg, "GPIO mode", ["input", "output"])


def valid_ugpio_view_table(arg: Any) -> List[List[str]]:
    try:
        return [list(map(str, row)) for row in list(arg)]
    except Exception:
        raise_error("<skipped>", "GPIO view table")
