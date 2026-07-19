import tkinter as tk

def main():
    root = tk.Tk()
    root.title("Grand Theft Auto V")
    root.geometry("800x600")
    
    label = tk.Label(
        root, 
        text="Fake 'Grand Theft Auto V' Window\nKeep this window open to test/debug the tool.", 
        font=("Segoe UI", 12),
        pady=50
    )
    label.pack()
    
    root.mainloop()

if __name__ == "__main__":
    main()
