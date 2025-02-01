System maintained by Robert, lead prop and maintenance technician 

# Kiosk System: A Multi-Room Escape Room Management Solution

This repository contains the code for a sophisticated kiosk system designed for multi-room escape room management. It incorporates a variety of features to streamline gameplay, enhance the experience, and provide robust control to administrators, with constant visual feedback.

## Core Functionality

*   **Multi-Room Support:** The system is designed to handle multiple independent escape rooms. Each room can have its unique set of props, puzzles, video backgrounds, audio tracks, and hints. Rooms can be assigned to individual kiosks using the admin interface.

*   **Kiosk Registration and Management:** Kiosks automatically announce themselves to the network upon startup, and are displayed on the administrator interface. The system maintains a live state of each registered kiosk, along with details such as room assignments and game progress. Individual kiosks can be remotely rebooted from the admin panel. A mini-timer display and a help request indicator are also shown in this list.

*   **Comprehensive Remote Control:** The system allows for comprehensive remote management of each kiosk from a central administrator panel, with immediate visual updates to confirm changes:
    *   **Game Timer Controls:**  Start, pause, or stop game timers for each room, and also precisely set the time remaining, using a 'Set Time' button. In addition, specific 'Add Time' or 'Reduce Time' buttons are present.
    *   **Background Music:** Control background music for each room, which is loaded automatically upon game start, and can be toggled on or off from the admin interface at any time. The admin receives immediate visual confirmation of toggling state on the admin interface.
    *   **Introductory Videos:** Play introductory videos for each room, allowing for customized intros, or a default 'global' intro. Videos are also accompanied with audio that is synchronized with the video.
    *    **Hint System:** Send visual hints (text and images) displayed on the kiosk; triggered by player initiated help requests. These hints appear in the same style as a video solution, and will automatically clear after the message has been displayed for a short time. An audio notification will also be played on the kiosk.
    *   **Audio Cues:** Send targeted audio cues (voiceovers, sound effects) to specific kiosks, ensuring that these cues are only played on the assigned device, and that these sounds do not interfere with other audio playback such as video or music.
    *  **Video Solutions:** Send video solutions to specific props. These videos are displayed on the kiosk, using a similar display to the hint system.
    *    **Clear Hints:**  Clear all hints from the kiosk interface, and clear its internal state.

*   **Robust Multi-Channel Audio:** The system is designed with multiple audio channels to ensure all audio streams are smooth and uninterrupted with a clear priority system:
    *   **Background Music:**  Each room has its unique looping background music. The music will start automatically when a timer is started. Background music will fade out when a video is played, and will smoothly fade in when complete. An admin may also toggle the music on/off instantly.
    *    **Sound Effects:** Plays sound effects on-demand from the administrator UI, triggering an sfx on the kiosk.
    *   **Audio Clues:**  Sends audio clues (voiceovers, sound cues) which are played on a dedicated audio channel.
    *   **Video Audio:** Automatically extracts and synchronizes the audio from videos, playing on a dedicated video channel and muting other audio.

*   **Real-Time Video Streaming:** The admin interface can receive a live video feed from each kiosk’s camera, enabling real-time monitoring of gameplay. The camera stream is low latency and the interface provides a single button to toggle this feature on or off.

*  **Synchronized Video Playback:** The system handles full screen video playback with synchronized audio. When a video is playing, the other background audio will be gently faded out, before being faded back in at the end of the video. Video playback can be skipped by clicking the video display area on the client side. This skip functionality is disabled on intro videos.
   
*   **Hint System:** Players initiate the hint system via an on-screen help button.
    *   When the help button is pressed, the player sees an immediate confirmation message on the kiosk, along with an audio cue.
    *   The admin receives a notification that a player requires a hint, which they may then respond to.
    *   Hints can be text, image-based, or both.
    *   A built-in cooldown system limits help requests for a period of time after a request is made, or when a new hint is received by the kiosk.
     * The system uses a custom PyQT overlay, which is used to display these hints on the player screen.
    *   The admin panel shows a timer for how long the cooldown is active for, along with the number of hints that have been requested.
    *  Admins can send pre-configured saved hints or custom hints which can be saved for later use.
   *   Hints can be audio based and played immediately, or video solutions, which are opened by the player when they choose to.

*   **Centralized Content Management:** All game content (videos, audio, images, hints) is stored on the administrator server and dynamically synchronized with kiosks.
    *   File synchronization is performed automatically when the system detects changes on the admin side.
    *   Kiosks download these content changes automatically using a content-hash based mechanism which only downloads updated content.
    *   Content is transferred over a lightweight HTTP protocol to improve transfer speeds. Kiosks use a unique identifier to register and download content as needed.

*   **Automated Game Start:** The system can be configured to start gameplay automatically when a room is assigned, triggered after an introductory video has been completed. This function may be enabled or disabled at any time on the admin interface. If enabled, the system will not automatically trigger after that first game start.

*   **Prop Control:** The admin interface allows remote control of the props in the selected room. Controls are provided to start, reset, activate, and finish props. Specific props are tied to specific MQTT endpoints, all predefined based on the current room selected. Communication between the admin and the individual props is performed with a lightweight JSON over MQTT implementation.

*  **Advanced Visual Feedback:** The system utilizes a PyQT overlay that will appear over the primary Tkinter window, and these components may be updated independently from the UI. The overlay features a consistent visual look for each feature.
    *   A rotating game timer that is displayed in the top-right corner of the screen.
    *  A rotating "Help" button that appears only when appropriate.
    *   Clear and concise temporary messages and modal windows, such as hint messages.
   *   Rotation to align with the 9:16 ratio.

*   **Detailed Stats Tracking:** The admin UI provides a comprehensive overview of each kiosk:
    *   Real-time timer status and the time remaining.
    *   The number of hints that have been requested (and received).
    *   If a hint request is currently pending by the player.
    *   The current timer state (running or stopped).
    *  The number of touch inputs that the screen has recorded.
    *   If background music is playing or paused.
    *   If Auto-Start is enabled.
    *   The time since the last in game "progress" was registered.
    *   The last prop that was activated in the room.
    *   The UI uses room-specific colour palettes to clearly mark active devices on the overview.
   *  Data is pushed to the admin side frequently.

*  **Password Protected Hint System:** All settings and hint management systems are secured behind a simple password protection. Passwords may be changed in the settings interface, and are saved via a hash.

*   **Persistent Room Assignments:** Rooms assigned to specific kiosks will persist across restarts, enabling seamless gameplay. The current room assignment is saved in local storage.

*   **Robust Architecture:** The system is built with a clear separation of concerns.
    *   A modular design facilitates easy integration of new features.
    *   Error handling minimizes interruptions. If a connection is lost to a client, the system will automatically retry after a brief pause.
    *   Asynchronous threading prevents user interface freezes, even during complex operations.
    *   All modules utilize a consistent logging method so that troubleshooting is easier.
    * All messages between client and server are transmitted using JSON encoding.

## Administrator Interface

The administrator interface is designed for efficient management and monitoring of the escape room system. It includes:

*   **Kiosk Overview Panel:** A panel showing all connected kiosks with the machine name, current room assignment (if any), a "Reboot" button, a mini timer and a "help requested" indicator for quick reference. Selecting a device in the overview will load its full interface below.

*   **Room Assignment:** Assign any connected kiosk to a room via the dropdown on its mini panel.

*   **Stats and Controls Section:**  A comprehensive control panel allowing you to manage device state, including audio and video, set timers, and send hints.

*   **Manual Hint Sending:** The Manual Hint section includes a text box, along with an image upload and preview. When the "Send" button is clicked, this text and/or image is sent to the selected kiosk. An option to 'clear' the text box is available. The 'Save' option allows you to save the current text and image to a custom library.

*  **Saved Hints Library:** Access a library of previously saved hints. These hints are categorized by the rooms and the specific props they are linked to, enabling efficient use of repeated hints. A simple search box is also available to easily find items.
   * Clicking on an item in the list will display a preview of the full text in the box, and if available, a small version of any linked image.
  * Selecting an item in the library will clear the text in the custom entry box, before setting the value of the selected entry. This allows for rapid creation of custom hints.

*   **Audio Clue Interface:** Browse and select audio files, which are pre-organized by room and specific props. These audio files may then be sent to the selected device.

*  **Video Solution Interface:** Choose from a list of relevant videos relating to a particular prop in a specific room. The dropdown list is updated automatically based on the device that is currently selected. Clicking on this will send the video to the device for immediate playback.

*  **Live Video Feed:** Toggles the live camera feed for the current device. This visual feed provides feedback about how players are progressing and offers a live view of the room.
 
*   **Remote Timer Controls:** Set specific durations for games via a dedicated 'Set Time' button, pause or resume using the ‘Start/Stop’ buttons and add or reduce time using the ‘+’ and ‘-‘ buttons.

*   **Audio and Visual Control:** Toggle background music, play specific videos, and trigger pre-recorded sounds. The music toggle allows for immediate switching between the 'playing' and 'stopped' state and provides visual confirmation.

*   **Reboot Functionality:** Allows remote rebooting of individual kiosks, using a hardcoded IP address. The "Reboot" button requires a confirmation click, and has a brief delay to prevent accidental reboots.

*   **Settings Interface:** This menu may be accessed via an icon in the top panel, prompting for a password before proceeding. The settings interface allows you to change the current password.
 
*   **Automatic Timer/Prop Synchronization:** When a timer is started for any given room, the system automatically loads the background music for that room. All other props for that room will also be loaded.

*   **Automatic Updates:** The file sync feature downloads new files as soon as they're available on the admin side, checking for file differences based on their unique content hash. Kiosks will download only changed files, or remove old ones, and upon completion, the UI is reset.

## Implementation Details

*   **Programming Languages:** The system is written in Python using `tkinter` for the main interface and `PyQt5` for the overlay, along with `paho-mqtt` for prop communication and `cv2` for video streaming.

*   **Network Communication:** Utilizes UDP for discovery and general messaging with JSON payloads, while TCP is used for video and audio data streaming.

    * All data transfer is performed over a lightweight protocol to optimize speed and minimize latency.
*   **Media Handling:** Uses the `pygame` library for audio playback and handling, and the `cv2` and `imageio-ffmpeg` libraries for video. The system prioritizes video playback by reducing other audio volumes.
*   **State Management:** Keeps a real-time track of each kiosk’s status to drive the live UI updates and messaging.
*   **File Synchronization:** Uses a custom mechanism to check for content updates, send, and delete files between the server and kiosks, using a lightweight content-hashing system. Only changed files are downloaded.
* **Touchscreen Handling:** The system tracks touch inputs to the screen for statistical purposes, however, touch is not used for core gameplay functions. Touch is used to skip video content, or trigger actions in the interface.
*   **Overlay Technology:**  A persistent graphical overlay is used to handle the timer, help button and hints. This overlay is a fully separate graphics layer, and allows for smooth animations and proper positioning of elements. This is a PyQT5 application, and is designed to provide a more flexible UI than standard Tkinter components.
*   **Audio Channels:** The system utilizes dedicated audio channels to ensure that all audio (sfx, cues, video and music) plays smoothly, and that the sounds are correctly prioritized. Background music is muted during video playback, and automatically fades out.

## Kiosk Initial State

Upon starting up, the kiosk will display a 'Waiting For Room Assignment' message. When a room has been assigned from the admin interface, the kiosk will download the assigned room's content, and prepare itself for gameplay, starting the assigned timer and playing any introductory videos.

## Kiosk File Synchronization Feedback

While updating files, the kiosk does not provide any feedback to the player about ongoing download/synchronization. The system will download and apply changes as quickly as possible in the background. All files will be downloaded before a reset message is sent to the client device, after which the kiosk will refresh its UI.

## Video Playback Feedback

The video playback is designed to be as seamless as possible. In 'solution videos', the player will have the ability to skip the video content via a simple click, whereas introductory videos may not be skipped. The video output will always fill the entire display area.
