<div align="center">

# Pixiv Downloader Web App

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Flask](https://img.shields.io/badge/Backend-Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![Tailwind](https://img.shields.io/badge/Frontend-Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)
### **Disclaimer**: 
This project is for educational purposes only. The author is not affiliated with Pixiv Inc. Use at your own risk.
**A robust, containerized solution for archiving, viewing, and managing artwork from Pixiv.**

[Features](#features) • [Installation](#setup--installation) • [Usage](#usage) • [Structure](#project-structure)

---
</div>

## 🚀 Overview

This project offers a modular web application designed to recursively fetch artworks, manage downloads with tag filtering, and present them in a modern, responsive gallery. Built on a **Python Flask** backend and powered by **PhotoSwipe** on the frontend, the entire stack is fully dockerized for instant deployment.

## ✨ Features

| Category | Functionality |
| :--- | :--- |
| **Core Engine** | **Recursive Downloading** to specified depths with concurrent processing. |
| **Filtering** | Smart **Tag Filtering** (Regex Blacklist/Whitelist) to curate content automatically. |
| **Interface** | Clean, responsive UI built with **Tailwind CSS** featuring infinite scrolling. |
| **Viewing** | High-performance **Lightbox Viewer** with zoom, pan, and touch support. |
| **Management** | Mark images as **Favorites** to persist them; one-click **Cleanup** for viewed non-favorites. |
| **Tracking** | Automatic **Viewed Tracking** (dimmed in gallery) and persistent history. |
| **Architecture** | Modular design separating Core Logic, Data, API, and UI. |

## 🛠️ Tech Stack

* **Containerization:** Docker, Docker Compose
* **Backend:** Python 3.11, Flask, SQLite
* **Frontend:** HTML5, JavaScript (ES6 Modules), Tailwind CSS
* **Key Libraries:** `pixivpy3`, `PhotoSwipe`, `requests`, `python-dotenv`

---

## 📦 Setup & Installation

### Prerequisites

* [Docker](https://www.docker.com/) and Docker Compose installed.
* A valid Pixiv Refresh Token.

### 1. Clone the Repository

Clone or extract the project files to your local machine.

### 2. Configure Environment

Create a file named `.env` in the root directory (adjacent to `docker-compose.yml`).

Add the following content to the file:

```ini
PIXIV_REFRESH_TOKEN=your_actual_refresh_token_here
USER_AGENT=PixivAndroidApp/5.0.234 (Android 11; Pixel 5)
DOWNLOAD_FOLDER=downloads
MAX_WORKERS=5
SECRET_KEY=change_this_to_a_random_string
```

Configuration Key:

* PIXIV_REFRESH_TOKEN: Your personal authentication token.

* USER_AGENT: Required to mimic a mobile device for API access.

* DOWNLOAD_FOLDER: Internal container path (default is standard).

* MAX_WORKERS: Number of concurrent download threads.

* API_DELAY: Pause between requests to avoid rate limiting.

* SECRET_KEY: Security key for Flask sessions.

### 3. Build and Run
Execute the build command in the root directory.

```Bash
docker-compose up --build
```
For subsequent runs in the background:

```Bash
docker-compose up -d
```
To stop the application:

```Bash
docker-compose down
```
🖥️ Usage
1. Access the UI: Navigate to http://localhost:5000.

2. Start Downloading:

  * Enter a Pixiv Artwork URL (e.g., https://www.pixiv.net/en/artworks/123456).

  * Set the Depth (recursion level).

  * Click Start Download.

3. Manage Content:

  * View: Click any thumbnail to open the PhotoSwipe lightbox.

  * Favorite: Toggle the heart icon to save an image permanently.

  * Cleanup: Use Delete Viewed to remove seen images that are not favorited.

### 📂 Project Structure
```Plaintext

pixiv_project/
├── .env                    
├── Dockerfile              
├── docker-compose.yml      
├── requirements.txt        
├── run.py                  
├── app/
│   ├── __init__.py         
│   ├── routes.py           
│   ├── core/
│   │   ├── __init__.py
│   │   └── downloader.py   
│   ├── data/
│   │   ├── __init__.py
│   │   └── database.py     
│   ├── templates/
│   │   └── index.html      
│   └── static/
│       ├── css/
│       │   └── style.css   
│       └── js/
│           └── main.js     
└── downloads/
```
### 💾 Data Persistence
The docker-compose.yml includes volume mappings to prevent data loss on container restarts:

* `./downloads`: Syncs downloaded media to your host machine.

* `./pixiv_media.db`: Syncs the SQLite database to preserve "Viewed" and "Favorite" states.
