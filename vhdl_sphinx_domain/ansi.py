""" ANSI codes to print terminal text with colors or effects
"""
ESC = '\u001b'  # escape sequence

# decorations
BOLD = ESC+'[01m'
UL = ESC+'[04m'  # underline
REV = ESC+'[07m'  # reverse

# colors
BLACK = ESC+'[30m'
RED = ESC+'[31m'
GREEN = ESC+'[32m'
ORANGE = ESC+'[33m'
BLUE = ESC+'[34m'
PURPLE = ESC+'[35m'
CYAN = ESC+'[36m'
LIGHTGREY = ESC+'[37m'
DARKGREY = ESC+'[90m'
LIGHTRED = ESC+'[91m'
LIGHTGREEN = ESC+'[92m'
YELLOW = ESC+'[93m'
LIGHTBLUE = ESC+'[94m'
PINK = ESC+'[95m'
LIGHTCYAN = ESC+'[96m'

# reset
NC = ESC+'[0m' # No color: disable colors and effects above
