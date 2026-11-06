"""What starts a session: SPACE on the keyboard, or a physical button on the Pi's GPIO pins.

Pi wiring for a button (any momentary push button):
  one leg  -> GPIO17 (physical pin 11)
  other leg -> any GND pin (e.g. physical pin 9)
Then set "gpio_pin": 17 in config.json. No resistor needed (the Pi's internal pull-up is used).
"""
import threading

SPACE = 32


class Trigger:
    def __init__(self, gpio_pin=None):
        self._pressed = threading.Event()
        self.button = None
        if gpio_pin is not None:
            try:
                from gpiozero import Button
                self.button = Button(int(gpio_pin), bounce_time=0.05)
                self.button.when_pressed = self._pressed.set
                print(f"[trigger] GPIO button on GPIO{gpio_pin}")
            except Exception as e:  # not on a Pi, or gpiozero missing
                print(f"[trigger] GPIO unavailable ({e}); keyboard only")

    def fired(self, key):
        """key = value from cv2.waitKey. True if SPACE or the button was pressed."""
        if key == SPACE:
            self._pressed.clear()
            return True
        if self._pressed.is_set():
            self._pressed.clear()
            return True
        return False

    def clear(self):
        """Ignore presses that happened mid-session (people mashing the button)."""
        self._pressed.clear()
