# EpisEERR - Episode Request Manager for Sonarr/Jellyseerr
Support This Project If you find this project helpful, please consider supporting it. Your contributions help maintain and improve the project. Any support is greatly appreciated! ❤️ https://buymeacoffee.com/vansmak Thank you for your support!

EpisEERR is a specialized middleware tool that enhances the integration between Jellyseerr (or Overseerr) and Sonarr by allowing users to request specific episodes rather than entire seasons.

## What Problem Does This Solve?

When users request TV shows in Jellyseerr, it sends the entire season to Sonarr, which downloads all episodes. EpisEERR interrupts this process, allowing you to:

1. Select only specific episodes you want
2. Cancel the full-season request in Jellyseerr
3. Monitor and search for only your chosen episodes
4. Request episodes directly via Telegram 

This is particularly useful for:
- Reality TV shows where you only want certain episodes
- Shows with mixed quality episodes
- Conserving disk space
- Quick add epecific episoded on the go (via direct Telegram requests)

## Important Notes Before Using

- **Tag Requirement**: EpisEERR creates a tag in Sonarr called "episodes" which is required for operation
- **Indexer Impact**: The script will temporarily send searches to your indexers and may initiate downloads (that get cancelled)
- **Resource Considerations**: If you have download limits with your provider, be aware this will use those resources (though likely less than full-season downloads would)
- **Continuous Operation**: The script must be running continuously to catch webhooks
- **Existing Tags**: This should not affect other tags you may be using in Sonarr

## Features

- Intercepts Jellyseerr TV requests via webhook
- Provides a Telegram interface for episode selection
- Allows direct episode requests via Telegram (without going through Jellyseerr)
   - Supports requesting multiple episodes across different seasons
- Automatically cancels the full season request in Jellyseerr (neccessary or seer app will get confused)
- Handles only the specific episodes you want

## Installation

### Prerequisites

- Sonarr
- Jellyseerr or Overseerr
- Python 3.7+
- Telegram Bot 

### Option 1: Manual Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/vansmak/episeerr.git
   cd episeerr
   ```

2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and edit it with your configuration:
   ```bash
   cp .env.example .env
   nano .env
   ```

4. Run the script:
   ```bash
   python episeerr.py
   ```
Systemd Service Setup

Create the systemd service file:

```bash
sudo nano /etc/systemd/system/episeerr.service
```
Copy the following content (replace your_username and /path/to/episeerr with your actual username and installation path):
```
[Unit]
Description=EpisEERR - Episode Request Manager for Sonarr/Jellyseerr
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/episeerr
ExecStart=/usr/bin/python3 /path/to/episeerr/episeerr.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Reload systemd, enable, and start the service:
```
sudo systemctl daemon-reload
sudo systemctl enable episeerr.service
sudo systemctl start episeerr.service
```

### Option 2: Docker Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/vansmak/episeerr.git
   cd episeerr
   ```

2. Copy `.env.example` to `.env` and edit with your configuration:
   ```bash
   cp .env.example .env
   nano .env
   ```

3. Build and start the Docker container:
   ```bash
   docker-compose up -d
   ```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure the following variables:

```
# Sonarr connection details
SONARR_URL=http://192.168.x.x:8989
SONARR_API_KEY=your_sonarr_api_key_here
SONARR_QUEUE_CHECK_INTERVAL=15
SONARR_QUEUE_MAX_CHECKS=8

# Overseerr/Jellyseerr connection details
OVERSEERR_URL=http://192.168.x.x:5055
OVERSEERR_API_KEY=your_overseerr_api_key_here

# Telegram bot details
TELEGRAM_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
TELEGRAM_ADMIN_IDS=comma,separated,admin,user,ids
```

### Jellyseerr/Overseerr Webhook Setup

1. In Jellyseerr, go to Settings > Notifications
2. Add a new webhook notification
3. Set the webhook URL to `http://your-episeerr-ip:5000/webhook`
4. Enable notifications for "Request Approved"
5. Save the webhook configuration

### Telegram Bot Setup

1. Create a new bot using [BotFather](https://t.me/botfather) in Telegram
2. Get your bot token and add it to the `.env` file
3. Start a chat with your bot
4. Get your chat ID using [@userinfobot](https://t.me/userinfobot) and add it to `.env`
5. Add your Telegram user ID to `TELEGRAM_ADMIN_IDS` to allow direct requests

## Usage

### Via Jellyseerr/Overseerr

1. Request a TV show (must be season only) through Jellyseerr and choose the tag "episodes"
2. Approve the request in Jellyseerr
3. EpisEERR will intercept the request and send you a Telegram message
4. Select the specific episodes you want via the Telegram interface
5. The script will configure Sonarr to download only those episodes

### Via Direct Telegram Requests

You can also request episodes directly through Telegram without going through Jellyseerr:

#### Single Season Request:
```
Show Title S01E05
```
or
```
Show Title S01EP01-03
```

#### Multi-Season Request:
```
Show Title S01E01,S01E03,S02E05
```
or
```
Show Title S01EP01-03,S02EP07,S03EP10-12
```

## Examples

### Jellyseerr Workflow

1. Request "This show 3" in Jellyseerr
2. Approve the request
3. Receive a Telegram message with all episodes from that season
4. Select episodes 2 and 8 via Telegram
5. EpisEERR will monitor and search for only episodes 2 and 8

### Direct Telegram Request

1. Send a message to your bot: `This show S03E02,S03E05`
2. The bot finds the show in Sonarr
3. It monitors and searches for episodes 2 and 5 from season 3
4. You get a confirmation message when this is complete

## Troubleshooting

- **Check logs**: Look in the `logs/` directory for `episeerr.log`
- **Webhook issues**: Ensure your Jellyseerr webhook is properly configured
- **Telegram issues**: Verify your bot token and chat ID are correct
- **Sonarr connection**: Check that EpisEERR can reach your Sonarr instance

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

Acknowledgments

Original concept and development by vansmak
Telegram integration and multi-episode functionality developed with assistance from Claude (Anthropic)

## License

[MIT License](LICENSE)
