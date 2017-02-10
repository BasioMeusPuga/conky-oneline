# conky-unitary
Conky config that shows statistics within the space of one line. Values falling outside defined scopes are automatically hidden. For extra minimalism.
Some (pacman) functions are Arch Linux specific.

## Requirements
* Conky: `conky-lua`
* Python 3: `python`
* DejaVu Sans Mono: `ttf-dejavu`

## Installation
* The `conkyrc` file is to be saved as `.conkyrc` wherever you want. Just point to it with `conky -c`.
* The python and lua scripts go into the `.conky` directory. This is not optional.
* `ConkyScript.py` has adjustable options in the first few lines. I seriously recommend going through them.
*Caveat emptor: I've set the update interval to 10s. I won't go lower than 5*

## Usage
`ConkyScript.py --help` will give you a list of supported functions. Currently, this config displays statistics for:

**Applications:**
* `qbittorrent`
* `clementine`
* `mpd`

**System Info:**
* Excess pacman cache size. (Default: 300 MiB)
* Available system updates - pacman
* Processes exceeding specified CPU utilization. (Default: 50)
* Current Wifi network. Tracks if the network is unstable, and if so, how long you've been disconnected from the internet.
* Free space for `/` and `/media/Data/Stored` (you probably don't want this)
* Service status - specify a list of services and notification state. conky will show their state.

**Inbuilt functions:**
* Calendar: Show / add / parse .ics for recurrent yearly events
* Countdown timer
