import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import time


BAUD = 115200


class LIOController:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "LIO V3 - Z Axis Controller"
        )

        self.root.geometry(
            "760x850"
        )

        self.ser = None

        self.keys_down = set()

        self.alignment_speed = 200
        self.sync_speed = 500
        self.acceleration = 250

        self.connect_serial()

        self.build_ui()

        self.bind_keyboard()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.quit
        )


    # ========================================================
    # CONNECT
    # ========================================================

    def connect_serial(self):

        ports = list(
            serial.tools.list_ports.comports()
        )

        if not ports:

            messagebox.showerror(
                "LIO",
                "No serial ports found."
            )

            return


        selected = None


        # Prefer the likely Nano USB ports.
        for port in ports:

            name = port.device.lower()

            if (
                "usbserial" in name or
                "usbmodem" in name
            ):

                selected = port.device

                break


        if selected is None:

            selected = ports[0].device


        try:

            self.ser = serial.Serial(
                selected,
                BAUD,
                timeout=0.1
            )

            # Arduino Nano commonly resets when
            # a serial port is opened.
            time.sleep(2)

            print(
                f"Connected to {selected}"
            )


        except serial.SerialException as exc:

            messagebox.showerror(
                "LIO",
                f"Serial connection failed:\n\n{exc}"
            )

            self.ser = None


    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(self):

        title = ttk.Label(
            self.root,
            text="LIO V3 Z AXIS",
            font=("Helvetica", 25, "bold")
        )

        title.pack(pady=15)


        self.status = ttk.Label(
            self.root,
            text=(
                "CONNECTED"
                if self.ser
                else "DISCONNECTED"
            ),
            font=("Helvetica", 14)
        )

        self.status.pack()


        # ====================================================
        # SYNC
        # ====================================================

        ttk.Label(
            self.root,
            text="SYNCHRONIZED MOTION",
            font=("Helvetica", 16, "bold")
        ).pack(pady=(25, 10))


        sync_frame = ttk.Frame(
            self.root
        )

        sync_frame.pack()


        ttk.Button(
            sync_frame,
            text="↑  BOTH UP",
            command=self.sync_up
        ).grid(
            row=0,
            column=0,
            padx=10,
            ipadx=30,
            ipady=15
        )


        ttk.Button(
            sync_frame,
            text="↓  BOTH DOWN",
            command=self.sync_down
        ).grid(
            row=0,
            column=1,
            padx=10,
            ipadx=30,
            ipady=15
        )


        # ====================================================
        # INDIVIDUAL
        # ====================================================

        ttk.Label(
            self.root,
            text="INDIVIDUAL MOTOR ALIGNMENT",
            font=("Helvetica", 16, "bold")
        ).pack(pady=(30, 10))


        ind = ttk.Frame(
            self.root
        )

        ind.pack()


        ttk.Label(
            ind,
            text="LEFT MOTOR",
            font=("Helvetica", 13)
        ).grid(
            row=0,
            column=0,
            padx=20,
            pady=5
        )


        ttk.Button(
            ind,
            text="LEFT ↑",
            command=self.left_up
        ).grid(
            row=1,
            column=0,
            padx=20,
            pady=5,
            ipadx=35,
            ipady=10
        )


        ttk.Button(
            ind,
            text="LEFT ↓",
            command=self.left_down
        ).grid(
            row=2,
            column=0,
            padx=20,
            pady=5,
            ipadx=35,
            ipady=10
        )


        ttk.Label(
            ind,
            text="RIGHT MOTOR",
            font=("Helvetica", 13)
        ).grid(
            row=0,
            column=1,
            padx=20,
            pady=5
        )


        ttk.Button(
            ind,
            text="RIGHT ↑",
            command=self.right_up
        ).grid(
            row=1,
            column=1,
            padx=20,
            pady=5,
            ipadx=35,
            ipady=10
        )


        ttk.Button(
            ind,
            text="RIGHT ↓",
            command=self.right_down
        ).grid(
            row=2,
            column=1,
            padx=20,
            pady=5,
            ipadx=35,
            ipady=10
        )


        # ====================================================
        # STOP
        # ====================================================

        ttk.Button(
            self.root,
            text="STOP EVERYTHING",
            command=self.stop
        ).pack(
            pady=25,
            ipadx=90,
            ipady=12
        )


        # ====================================================
        # ALIGNMENT SPEED
        # ====================================================

        ttk.Label(
            self.root,
            text="INDIVIDUAL ALIGNMENT SPEED"
        ).pack()


        self.align_scale = tk.Scale(
            self.root,
            from_=50,
            to=1500,
            resolution=25,
            orient=tk.HORIZONTAL,
            length=540,
            command=self.alignment_speed_changed
        )

        self.align_scale.set(
            self.alignment_speed
        )

        self.align_scale.pack()


        self.align_label = ttk.Label(
            self.root,
            text=(
                f"{self.alignment_speed} "
                "half-steps/sec"
            )
        )

        self.align_label.pack()


        # ====================================================
        # SYNC SPEED
        # ====================================================

        ttk.Label(
            self.root,
            text="SYNCHRONIZED SPEED"
        ).pack(pady=(15, 0))


        self.sync_scale = tk.Scale(
            self.root,
            from_=100,
            to=3000,
            resolution=50,
            orient=tk.HORIZONTAL,
            length=540,
            command=self.sync_speed_changed
        )

        self.sync_scale.set(
            self.sync_speed
        )

        self.sync_scale.pack()


        self.sync_label = ttk.Label(
            self.root,
            text=(
                f"{self.sync_speed} "
                "half-steps/sec"
            )
        )

        self.sync_label.pack()


        # ====================================================
        # ACCELERATION
        # ====================================================

        ttk.Label(
            self.root,
            text="ACCELERATION"
        ).pack(pady=(15, 0))


        self.accel_scale = tk.Scale(
            self.root,
            from_=25,
            to=3000,
            resolution=25,
            orient=tk.HORIZONTAL,
            length=540,
            command=self.accel_changed
        )

        self.accel_scale.set(
            self.acceleration
        )

        self.accel_scale.pack()


        self.accel_label = ttk.Label(
            self.root,
            text=(
                f"{self.acceleration} "
                "half-steps/sec²"
            )
        )

        self.accel_label.pack()


        # ====================================================
        # KEYBOARD
        # ====================================================

        ttk.Label(
            self.root,
            text=(
                "KEYBOARD CONTROL\n\n"
                "↑  = both UP\n"
                "↓  = both DOWN\n"
                "←  = left UP\n"
                "→  = right UP\n"
                "A  = left DOWN\n"
                "D  = right DOWN\n"
                "SPACE  = STOP\n"
                "Q / ESC  = quit\n\n"
                "Keyboard motion is momentary:\n"
                "hold the key to move, release to stop."
            ),
            justify=tk.CENTER
        ).pack(pady=25)


    # ========================================================
    # SERIAL SEND
    # ========================================================

    def send(self, command):

        if self.ser is None:

            return


        try:

            self.ser.write(
                (command + "\n").encode("ascii")
            )

            self.ser.flush()


        except serial.SerialException:

            self.status.config(
                text="SERIAL ERROR"
            )


    # ========================================================
    # SPEED CHANGES
    # ========================================================

    def alignment_speed_changed(
        self,
        value
    ):

        self.alignment_speed = int(
            float(value)
        )

        self.align_label.config(
            text=(
                f"{self.alignment_speed} "
                "half-steps/sec"
            )
        )

        self.send(
            f"VA{self.alignment_speed}"
        )


    def sync_speed_changed(
        self,
        value
    ):

        self.sync_speed = int(
            float(value)
        )

        self.sync_label.config(
            text=(
                f"{self.sync_speed} "
                "half-steps/sec"
            )
        )

        self.send(
            f"VS{self.sync_speed}"
        )


    def accel_changed(
        self,
        value
    ):

        self.acceleration = int(
            float(value)
        )

        self.accel_label.config(
            text=(
                f"{self.acceleration} "
                "half-steps/sec²"
            )
        )

        self.send(
            f"ACC{self.acceleration}"
        )


    # ========================================================
    # SYNCHRONIZED
    # ========================================================

    def sync_up(self):

        self.send("U")


    def sync_down(self):

        self.send("D")


    # ========================================================
    # INDIVIDUAL
    # ========================================================

    def left_up(self):

        self.send("LU")


    def left_down(self):

        self.send("LD")


    def right_up(self):

        self.send("RU")


    def right_down(self):

        self.send("RD")


    # ========================================================
    # STOP
    # ========================================================

    def stop(self):

        self.send("S")


    # ========================================================
    # KEYBOARD
    # ========================================================

    def bind_keyboard(self):

        self.root.bind(
            "<KeyPress-Up>",
            self.key_press
        )

        self.root.bind(
            "<KeyRelease-Up>",
            self.key_release
        )

        self.root.bind(
            "<KeyPress-Down>",
            self.key_press
        )

        self.root.bind(
            "<KeyRelease-Down>",
            self.key_release
        )

        self.root.bind(
            "<KeyPress-Left>",
            self.key_press
        )

        self.root.bind(
            "<KeyRelease-Left>",
            self.key_release
        )

        self.root.bind(
            "<KeyPress-Right>",
            self.key_press
        )

        self.root.bind(
            "<KeyRelease-Right>",
            self.key_release
        )

        self.root.bind(
            "<KeyPress-a>",
            self.key_press
        )

        self.root.bind(
            "<KeyRelease-a>",
            self.key_release
        )

        self.root.bind(
            "<KeyPress-d>",
            self.key_press
        )

        self.root.bind(
            "<KeyRelease-d>",
            self.key_release
        )

        self.root.bind(
            "<KeyPress-space>",
            self.key_stop
        )

        self.root.bind(
            "<KeyPress-Escape>",
            self.quit
        )

        self.root.bind(
            "<KeyPress-q>",
            self.quit
        )

        self.root.bind(
            "<KeyPress-Q>",
            self.quit
        )


    def key_press(self, event):

        key = event.keysym.lower()

        if key in self.keys_down:

            return

        self.keys_down.add(key)


        if key == "up":
            self.send("U")

        elif key == "down":
            self.send("D")

        elif key == "left":
            self.send("LU")

        elif key == "right":
            self.send("RU")

        elif key == "a":
            self.send("LD")

        elif key == "d":
            self.send("RD")


    def key_release(self, event):

        key = event.keysym.lower()

        self.keys_down.discard(key)


        if key in {
            "up",
            "down",
            "left",
            "right",
            "a",
            "d"
        }:

            self.stop()


    def key_stop(self, event):

        self.stop()


    # ========================================================
    # EXIT
    # ========================================================

    def quit(self, event=None):

        self.send("S")

        time.sleep(0.1)

        if self.ser is not None:

            try:
                self.ser.close()

            except Exception:
                pass

        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = LIOController(root)

    root.mainloop()