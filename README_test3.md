# Hand Gesture AR Defender 🖐️🎮

A computer-vision-based Augmented Reality (AR) tower defense game. The player uses hand gestures (pinching) captured via a webcam to interact with UI elements, type on a virtual keyboard, and destroy incoming enemies.

Built with **Python**, **OpenCV**, and **MediaPipe**.

---

## 📋 Table of Contents
1. [Features](#-features)
2. [Prerequisites & Installation](#-prerequisites--installation)
3. [How to Play](#-how-to-play)
4. [Project Architecture](#-project-architecture)
5. [Configuration & Tuning](#-configuration--tuning)
6. [Data Persistence](#-data-persistence)
7. [Troubleshooting](#-troubleshooting)

---

## 🌟 Features

* **Hand Tracking**: Real-time hand landmark detection using Google MediaPipe (optimized for performance).
* **Gesture Control**: Custom "Pinch" detection (Thumb + Index Finger) used for clicking buttons and attacking enemies.
* **Virtual Keyboard**: A gesture-controlled on-screen keyboard for user registration.
* **User Profiles**: JSON-based save system to store usernames, match history, and personal best scores.
* **State Machine System**: Robust flow control managing Login, Menus, Gameplay, and Game Over states.
* **Dynamic Difficulty**: Three difficulty levels (Easy, Normal, Hard) that adjust enemy speed and spawn rates.

---

## 🛠 Prerequisites & Installation

### Requirements
* **Python 3.7+**
* **Webcam**: A functional webcam connected to the computer.

### Installation Steps

1.  **Clone the repository** (or download the source code):
    ```bash
    git clone [https://github.com/yourusername/hand-game.git](https://github.com/yourusername/hand-game.git)
    cd hand-game
    ```

2.  **Install dependencies**:
    This project relies on `opencv-python`, `mediapipe`, and `numpy`.
    ```bash
    pip install opencv-python mediapipe numpy
    ```

3.  **Run the game**:
    ```bash
    python hand_game_full.py
    ```

---

## 🎮 How to Play

### 1. The Controls
Your **cursor** is the midpoint between your **Index Finger Tip** and **Thumb Tip**.
* **🔴 Red Hollow Circle**: Hand is **Open** (Hovering mode).
* **🟢 Green Solid Circle**: Hand is **Pinched** (Click/Attack mode).

### 2. The Game Flow
1.  **Login**: Use the virtual keyboard to type your username. Pinch the letters to type, pinch `ENTER` to confirm.
2.  **Main Menu**: Pinch "START GAME" to proceed or "RECORDS" to view stats.
3.  **Difficulty**: Select Easy, Normal, or Hard.
4.  **Gameplay**:
    * Red enemies spawn from the screen edges.
    * Move your hand cursor over an enemy.
    * **Pinch** your fingers to destroy it.
    * **Goal**: Prevent enemies from touching the green circle (Player) in the center.

---

## 🏗 Project Architecture

The code is structured into modular classes to allow for easy modification by collaborators.

### 1. `DataManager`
* **File**: `hand_game_full.py`
* **Purpose**: Handles File I/O.
* **Details**: Loads and saves `game_data.json`. It manages user registration, score updates, and deletion logic.

### 2. `Button` & `VirtualKeyboard`
* **Purpose**: UI Component classes.
* **Details**: 
    * `Button`: Handles drawing and collision detection (`is_hovering`).
    * `VirtualKeyboard`: Generates the A-Z grid and handles string manipulation for the username input.

### 3. `HandGame` (The Engine)
This is the main class containing the game loop and the State Machine.

#### Key Methods:
* **`detect_pinch(self, img, hand_lms)`**: 
    * Calculates Euclidean distance between landmarks 4 (Thumb) and 8 (Index).
    * **Debounce Logic**: Uses `self.hand_clicked_status` to ensure a pinch action registers as a **single click** rather than a continuous stream. You must open your hand to reset the click state.
* **`run(self)`**: 
    * The main `while True` loop.
    * Manages the **Game States**: `LOGIN` -> `MENU` -> `DIFFICULTY` -> `PLAYING` -> `GAME_OVER`.

---

## ⚙ Configuration & Tuning

Collaborators can tweak the `HandGame` class to adjust the game feel.

### Adjusting Pinch Sensitivity
If the camera is too far or too close, adjust the threshold in `__init__`:

```python
# Pixels distance between thumb and index to trigger a click
self.pinch_threshold = 40