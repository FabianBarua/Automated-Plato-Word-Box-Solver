from ui.app import App


if __name__ == "__main__":
    app = App()
    app.mainloop()

    # Cleanup on exit
    app.is_solving = False
    app.is_paused = False
    app.is_scanning = False
    app.controller.device_manager.stop_scrcpy()
