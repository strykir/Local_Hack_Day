# 🚀 Hand Game Ultimate: AR Space Defender

**Hand Game Ultimate** is an interactive Augmented Reality (AR) defense game powered by real-time Computer Vision.  
Using only your webcam, you control a spaceship and defend it from incoming enemies using hand gestures.

Built with **Python**, **OpenCV**, and **Google MediaPipe**.

---

## 📋 Table of Contents
1. [Features](#-features)
2. [Installation & Setup](#-installation--setup)
3. [How to Launch](#-how-to-launch)
4. [Gameplay & Controls](#-gameplay--controls)
5. [Enemy Types & Strategies](#-enemy-types--strategies)
6. [Account System](#-account-system)
7. [Secrets](#-secrets)
8. [Folder Structure](#-folder-structure)
9. [License](#-license)

---

## 🌟 Features

- **Gesture Recognition**: Detects both “Pinch” (precision attack) and “Fist” (heavy attack).
- **Fullscreen Adaptive UI**: Automatically scales UI elements to your screen resolution.
- **Local Profile System**: Create users, save history, and track progress.
- **Dynamic Difficulty**: Easy / Normal / Hard modes with different enemy spawn rates.
- **Customizable Skins**: Replace assets in the `icons/` folder to reskin enemies and ships.
- **Pause Menu**: Hover-based pause system with Resume, Restart, and Save & Quit options.

---

## 🛠 Installation & Setup

### 1. Prerequisites
- A PC or laptop with a functional webcam.
- **Python 3.8+** installed.
- Recommended: Conda for environment management.

---

### 2. Install Dependencies

A `requirements.yml` file is included for convenience.

#### **Option A (Recommended): Conda**
```bash
conda env create -f requirements.yml
conda activate hand-game
```

#### **Option B: Pip**
```bash
pip install opencv-python mediapipe numpy
```

---

## ▶️ How to Launch

1. Open your terminal or command prompt.
2. Navigate to the project's root directory.
3. Run the game:

```bash
python main.py
```

The game will launch in **Fullscreen Mode**.

> Press **ESC** at any time to instantly exit the game.

---

## 🕹 Gameplay & Controls

### 🎯 Objective
Protect your spaceship at the center of the screen.  
If **any enemy** touches the ship → **Game Over**.

---

### ✋ Gesture Controls

| Action               | Gesture                           | Visual Indicator                       | Target Type                |
|----------------------|------------------------------------|----------------------------------------|----------------------------|
| Precision Shot       | Pinch (thumb + index finger)       | Small **green circle**                 | Red / Standard enemies     |
| Heavy Strike         | Fist (closed hand)                 | Large **blue circle** + “FIST MODE”    | Blue / Armored enemies     |

---

### ⏸ Pause Menu

Hover your hand over the **pause icon ("II")** in the upper-right corner.

Pause options include:
- **Resume**
- **Restart**
- **Save & Quit**

---

## 👾 Enemy Types & Strategies

Image assets are dynamically loaded from the `icons/` directory.

### **1. The Swarm — Pinch Type**
- Folder: `icons/pinch/`
- Default Appearance: Red circle
- Behavior: Fast and numerous
- Counter: **Use Pinch gestures**

---

### **2. The Blockade — Fist Type**
- Folder: `icons/fist/`
- Default Appearance: Blue square
- Behavior: Heavy armor / special enemy
- Counter: **Use Fist (Pinch has no effect)**

---

## 👤 Account System

User data is stored in:

```
user_data/users.json
```

### Features:
- **Register** using an on-screen virtual keyboard
- **Guest Mode** (SKIP) to start instantly — Guest scores are not saved
- **Records Menu**:
  - Displays high scores for each difficulty
  - Allows switching between users
  - Allows deleting users

---

## 🤫 Secrets

A hidden event exists when playing on **Normal** or **Hard** difficulty:

### 🎯 Trigger Condition
Score **≥ 64**

### 👹 Event — “Deep Space Anomaly”
There is a **90% chance** that a massive Boss enemy appears.

- Asset: `icons/special/special_enemy.png`

### 🎁 Reward  
If you manage to defeat the Boss using a **Fist Strike**, your spaceship will undergo a **temporary evolution** for the entire session:

- Asset: `icons/special/special_ship.png`

Good luck, Commander.

---

## 📁 Folder Structure

```text
/Game_Root
├── icons/
│   ├── pinch/          # Pinch-type enemy assets
│   ├── fist/           # Fist-type enemy assets
│   ├── spaceship/      # Player ship skins
│   └── special/        # Boss & evolution assets
├── src/
│   ├── DataManager.py  # Save/load system
│   └── Components.py   # Game core components
├── user_data/          # Auto-generated user data
├── main.py
└── requirements.yml
```

---

## 📝 License
This project is intended for personal and educational use.  
For commercial use, please contact the author.
