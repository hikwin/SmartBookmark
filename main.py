import ttkbootstrap as tb
from main_app import BookmarkApp

def main():
    # Setup Window with Superhero theme
    root = tb.Window(themename="superhero")
    
    # Initialize Application
    app = BookmarkApp(root)
    
    # Start main loop
    root.mainloop()

if __name__ == "__main__":
    main()
