# SPDX-FileCopyrightText: 2021 Sandy Macdonald
#
# SPDX-License-Identifier: MIT

"""
`Pimoroni's Pico RGB Keypad CircuitPython library`
====================================================

CircuitPython driver for the Pimoroni Pico RGB Keypad.
From Sandy Macdonald's Keybow 2040 library.

Drop the rgbkeypad.py file into your `lib` folder on your `CIRCUITPY` drive.

* Author: Sandy Macdonald
* Author: Angainor Dev

Notes
--------------------

**Hardware:**

* Pimoroni Pico RGB Keypad
  <https://shop.pimoroni.com/products/>_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for Raspberry Pi Pico:
  <https://circuitpython.org/board/raspberry_pi_pico/>_

* Adafruit Dotstar circuit python library

"""

from typing import Callable

import time
import board
import busio

from digitalio import DigitalInOut, Direction
from adafruit_bus_device.i2c_device import I2CDevice
from adafruit_dotstar import DotStar

NUM_KEYS = 16
DEFAULT_BRIGHTNESS = 0.05
ENABLE_SLEEP = True


class RGBKeyPad():
    """Represents the keypad and hence a set of Key instances"""
    def __init__(self):

        # Device setup
        self.cs = DigitalInOut(board.GP17)
        self.cs.direction = Direction.OUTPUT
        self.cs.value = 0
        self.pixels = DotStar(board.GP18, board.GP19, 16, brightness=DEFAULT_BRIGHTNESS, auto_write=True)
        i2c = busio.I2C(board.GP5, board.GP4)
        self.device = I2CDevice(i2c, 0x20)
    
        # Variables
        self.states = [0] *16
        self.time_of_last_press = time.monotonic()
        self.time_since_last_press = None
        self.last_led_states = None

        # Sleep variables
        self.led_sleep_enabled = True
        self.led_sleep_time = 1
        self.sleeping = False
        self.was_asleep = False

        # Initialises & attaches the indiviual keys
        self.keys = [Key(i, self.pixels, self.states[i]) for i in range(NUM_KEYS)]

    def update(self):
        """Updates the state of the keypad and all of its keys.
        
        Call this in each iteration of your while loop to update"""

        with self.device:
            self.device.write(bytes([0x0]))
            result = bytearray(2)
            self.device.readinto(result)
            all_states = result[0] | result[1] << 8
            for i in range(0,16):
                if not (1 << i) & all_states:
                    self.states[i] = 1
                else:
                    self.states[i] = 0

        for _key in self.keys:
            _key.update()

        if ENABLE_SLEEP:
            self.sleep_handler()


    def sleep_handler(self):
        """Handles the sleep behaviour of the keypad."""
        if self.any_pressed():
            self.time_of_last_press = time.monotonic()
            self.sleeping = False

        self.time_since_last_press = time.monotonic() - self.time_of_last_press

        # If LED sleep is enabled, but not engaged, check if enough time
        # has elapsed to engage sleep. If engaged, record the state of the
        # LEDs, so it can be restored on wake.
        if self.led_sleep_enabled and not self.sleeping:
            if self.time_since_last_press > self.led_sleep_time:
                self.sleeping = True
                self.last_led_states = [k.rgb if k.lit else [0, 0, 0] for k in self.keys]
                self.set_all(0, 0, 0)
                self.was_asleep = True

        # If it was sleeping, but is no longer, then restore LED states.
        if not self.sleeping and self.was_asleep:
            for k in range(NUM_KEYS):
                self.keys[k].set_led(*self.last_led_states[k])
            self.was_asleep = False

    def set_led(self, number, r, g, b):
        """Set an individual key's LED to an RGB value by its number."""

        self.keys[number].set_led(r, g, b)

    def set_all(self, r, g, b):
        """Sets all of the keypad's LEDs to an RGB value"""

        if not self.sleeping:
            for _key in self.keys:
                _key.set_led(r, g, b)
        else:
            for _key in self.keys:
                _key.led_off()

    def clear_all(self):
        """Turns off all of the keypad's LEDs"""
        for _key in self.keys:
            _key.led_off()

    def get_states(self) -> list[bool]:
        """Get the states of all the keys on the keypad.
        
        Returns a list of the key states (0=not pressed, 1=pressed)"""
        _states = [_key.key_state for _key in self.keys]
        return _states

    def get_pressed(self)-> list[int]:
        """Returns a list of key numbers currently pressed"""

        _pressed = [_key.number for _key in self.keys if _key.key_state]
        return _pressed

    def any_pressed(self) -> bool:
        """Returns True if any key is pressed, False if none are pressed."""

        return any(self.get_states())

    def none_pressed(self):
        """Returns True if none of the keys are pressed, False is any key is pressed."""
        return not any(self.get_states())

    @staticmethod
    def on_press(_key, state:str = 'default', handler=None):
        """Attaches a press function to a key, via a decorator.
        
        This is stored as `key.press_function` in the key's attributes, and runs if triggered.
        
        It can be attached as follows:

            @RGBKeyPad.on_press(key, state='state_name')
            def press_handler(key):
                do something

        The `state` parameter is optional and can be used to specify a state string that will change
        what press function is attached given the state.
        """
        if _key is None:
            return

        def attach_handler(a_handler):
            _key.press_functions[state] = a_handler

        if handler is not None:
            attach_handler(handler)
        else:
            return attach_handler

    @staticmethod
    def on_release(_key, state:str = 'default', handler=None):
        """Attaches a release function to a key, via a decorator.
        
        This is stored as `key.release_function` in the key's attributes, and runs if triggered.

        @RGBKeyPad.on_release(key, state='state_name')
        def release_handler(key):
            do something
        """

        if _key is None:
            return

        def attach_handler(a_handler):
            _key.release_functions[state] = a_handler

        if handler is not None:
            attach_handler(handler)
        else:
            return attach_handler

    @staticmethod
    def on_hold(_key, state:str = 'default', handler=None):
        """Attaches a hold function to a key, via a decorator.
        
        This is stored as `key.hold_function` in the key's attributes, and runs if triggered.

        @RGBKeyPad.on_release(key, state='state_name') 
        def hold_handler(key):
            do something
        """

        if _key is None:
            return

        def attach_handler(a_handler):
            _key.hold_functions[state] = a_handler

        if handler is not None:
            attach_handler(handler)
        else:
            return attach_handler


class Key:
    """Represents a key on Keypad.

    :param number: the unique key number (0-15) to associate with the key
    :param pixels: the dotstar instance for the LEDs
    :param current_state: the current state of the key (0 or 1)
    :param board_state: the state of the board (default or other)
    """
    def __init__(self, number: int, pixels: DotStar, key_state: bool, board_state: str = 'default'):
        self.number = number
        self.pixels = pixels
        self.current_state = key_state
        self.board_state = board_state
        self.key_state = 0
        self.pressed = 0
        self.last_state = None
        self.time_of_last_press = time.monotonic()
        self.time_since_last_press = None
        self.time_held_for = 0
        self.held = False
        self.hold_time = 0.75
        self.modifier = False
        self.rgb = [0, 0, 0]
        self.lit = False
        self.xy = self.get_xy()
        self.x, self.y = self.xy
        self.led_off()
        self.press_functions: dict[str, Callable] = {'default': None}
        self.release_functions: dict[str, Callable]= {'default': None}
        self.hold_functions:dict[str, Callable] = {'default': None}
        self.press_func_fired = False
        self.hold_func_fired = False
        self.debounce = 0.125
        self.key_locked = False


    def update(self):
        """Updates the state of the key and all of its attributes."""

        self.time_since_last_press = time.monotonic() - self.time_of_last_press

        # Keys get locked during the debounce time. This is to prevent rapid key presses.
        if self.time_since_last_press < self.debounce:
            self.key_locked = True
        else:
            self.key_locked = False

        self.key_state = self.current_state
        self.pressed = self.key_state
        update_time = time.monotonic()

        # If there's a `press_function` attached, then call it,
        # returning the key object and the pressed state.
        if self.press_functions is not None and self.pressed and not self.press_func_fired and not self.key_locked:
            self.press_functions[self.board_state](self)
            self.press_func_fired = True
            # time.sleep(0.05)  # A little debounce

        # If the key has been pressed and releases, then call
        # the `release_function`, if one is attached.
        if not self.pressed and self.last_state:
            if self.release_functions is not None:
                self.release_functions[self.board_state](self)
            self.last_state = False
            self.press_func_fired = False

        if not self.pressed:
            self.time_held_for = 0
            self.last_state = False

        # If the key has just been pressed, then record the
        # `time_of_last_press`, and update last_state.
        elif self.pressed and not self.last_state:
            self.time_of_last_press = update_time
            self.last_state = True

        # If the key is pressed and held, then update the
        # `time_held_for` variable.
        elif self.pressed and self.last_state:
            self.time_held_for = update_time - self.time_of_last_press
            self.last_state = True

        # If the `hold_time` threshold is crossed, then call the
        # `hold_function` if one is attached. The `hold_func_fired`
        # ensures that the function is only called once.
        if self.time_held_for > self.hold_time:
            self.held = True
            if self.hold_functions is not None and not self.hold_func_fired:
                self.hold_functions[self.board_state](self)
                self.hold_func_fired = True
        else:
            self.held = False
            self.hold_func_fired = False

    def get_xy(self):
        # Returns the x/y coordinate of a key from 0,0 to 3,3.

        return number_to_xy(self.number)

    def get_number(self):
        # Returns the key number, from 0 to 15.

        return xy_to_number(self.x, self.y)

    def is_modifier(self):
        # Designates a modifier key, so you can hold the modifier
        # and tap another key to trigger additional behaviours.

        if self.modifier:
            return True
        else:
            return False

    def set_led(self, r, g, b):
        # Set this key's LED to an RGB value.

        if [r, g, b] == [0, 0, 0]:
            self.lit = False
        else:
            self.lit = True
            self.rgb = [r, g, b]

        self.pixels[self.number] = (r, g, b)

    def led_on(self):
        # Turn the LED on, using its current RGB value.

        r, g, b = self.rgb
        self.set_led(r, g, b)

    def led_off(self):
        # Turn the LED off.

        self.set_led(0, 0, 0)

    def led_state(self, state):
        # Set the LED's state (0=off, 1=on)

        state = int(state)

        if state == 0:
            self.led_off()
        elif state == 1:
            self.led_on()
        else:
            return

    def toggle_led(self, rgb=None):
        # Toggle the LED's state, retaining its RGB value for when it's toggled
        # back on. Can also be passed an RGB tuple to set the colour as part of
        # the toggle.

        if rgb is not None:
            self.rgb = rgb
        if self.lit:
            self.led_off()
        else:
            self.led_on()

    def __str__(self):
        # When printed, show the key's state (0 or 1).
        return self.key_state


def xy_to_number(x, y):
    # Convert an x/y coordinate to key number.
    return x + (y * 4)


def number_to_xy(number):
    # Convert a number to an x/y coordinate.
    x = number % 4
    y = number // 4
    return x, y


def hsv_to_rgb(h, s, v):
    # Convert an HSV (0.0-1.0) colour to RGB (0-255)
    rgb = [v, v, v]  # s = 0, default value

    i = int(h * 6.0)

    f = (h * 6.) - i
    p, q, t = v * (1. - s), v * (1. - s * f), v * (1. - s * (1. - f))
    i %= 6

    if i == 0:
        rgb = [v, t, p]
    if i == 1:
        rgb = [q, v, p]
    if i == 2:
        rgb = [p, v, t]
    if i == 3:
        rgb = [p, q, v]
    if i == 4:
        rgb = [t, p, v]
    if i == 5:
        rgb = [v, p, q]

    rgb = tuple(int(c * 255) for c in rgb)

    return rgb   