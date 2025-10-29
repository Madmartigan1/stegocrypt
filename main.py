# main.py
from tkinter import Tk
from app_gui import App

def main():
    root = Tk()
    # Quick-exit keybindings (global)
    root.bind("<Escape>", lambda e: root.destroy())
    root.bind("<Control-q>", lambda e: root.destroy())
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
