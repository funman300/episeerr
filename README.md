Dev branch is developmental, consider it beta
#  <img src="https://github.com/Vansmak/OCDarr/assets/16037573/f802fece-e884-4282-8eb5-8c07aac1fd16" alt="logo" width="200"/>

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/vansmak)


🎯 Episode Management and arr consolidation
OCDarr isn't just another media management tool—it's a precision instrument for curating your sonarr library with granularity.
🔬 Rule-Based Episode Control, the heart of OCDarr
Most media management tools operate on an all-or-nothing approach. OCDarr revolutionizes this with its dynamic, per-show rule system:

> Granular Episode Selection: Choose exactly which episodes you want
> Intelligent Cleanup: Automatically manage your library based on your viewing habits
> Flexible Rules: Create custom management strategies for different shows

Rule Components: Your Media, Your Rules  #control what happens as you watch a series

Get Option: Control how many upcoming episodes to prepare

  - 1: Just the next episode
  - 3: Next three episodes
  - season: Full season
  - all: Everything upcoming                                                  


Action Option: Define how episodes are handled

  - monitor: Passive tracking
  - search: Active download and monitoring


Keep Watched: Manage post-viewing library

  - 1: Keep only the last watched episode
  - 2: Keep last two episodes
  - season: Retain current season
  - all: Keep everything


Monitor Watched: Tracking behavior after watching

  - true: Keep watched episodes monitored
  - false: Automatically unmonitor after viewing
                                    


🎬 Adaptive Episode Request Workflows # control precisely what you want to add for a new series
OCDarr supports multiple request scenarios with intelligent handling:
External Requests (Jellyseerr/Overseerr)
**use episodes tag when requestiing something from seer, sonarr, 3rd party apps if you want to control what your request down to individual episodes
With "episodes" tag:

 - Precise episode selection
 - Unmonitor all initial episodes
 - Cancel automatic downloads
 - User-guided episode monitoring


Without "episodes" tag:

- Instant addition to default rule
- Automatic management based on predefined preferences



Internal Requests (OCDarr Interface)

 - Identical powerful selection mechanism
 - Pilot episode handling
 - Granular episode monitoring

🌟 Real-World Scenario
  Example: You're watching "Breaking Bad"
  
  You want only the next episode ready
  Automatically clean up watched episodes
  Keep the current season
  Stop tracking after you've finished

Traditional Solution: Download entire seasons, manual cleanup
OCDarr Solution: Intelligent, automated, personalized management
🔑 Key Differentiators

🎯 Episode-level control
🧹 Automatic library management
🔧 Highly configurable rules
🚀 Proactive episode preparation

OCDarr isn't just a tool—it's your personal media librarian.

- Want the next episode ready when they finish the current one
- Prefer to keep their media library tidy
- Don't need to keep entire seasons after watching
- Want different management rules for different shows
- Use with overseer or Jellyseer to manage at the episode level instead of full season

_Not designed for media hoarders or large household servers with multiple users at different points in series._
_Use is intended for owned media or paid supscription services._
  

### Interface Preview
![ocd](https://github.com/user-attachments/assets/cd7b5c0f-275f-4222-99e6-40fd76c6f495)


## 📋 Requirements


- Sonarr v3
- Either:
  - Plex + Tautulli
  - OR Jellyfin #not yet
- Docker environment
- Overseerr/Jellyseerr (optional, for automatic rule assignment)

## 🚀 Installation

### Option 1: Docker Hub (Recommended)

```bash
# Pull the image
docker pull vansmak/ocdarr:amd64_dev

# Run the container
docker run -d \
  --name ocdarr \
  --env-file .env \
  --env CONFIG_PATH=/app/config/config.json \
  -p 5001:5001 \
  -v ${PWD}/logs:/app/logs \
  -v ${PWD}/config:/app/config \
  -v ${PWD}/temp:/app/temp \
  --restart unless-stopped \
  vansmak/ocdarr:latest
```
Option 2: Build from Source
```
git clone https://github.com/Vansmak/OCDarr.git
cd OCDarr
git checkout dev
docker-compose up -d --build
```
⚙️ Configuration
Environment Variables
Create a .env file:
```
SONARR_URL=http://sonarraddress
SONARR_API_KEY=your_sonarr_api_key

JELLYSEERR_URL=http://jellyoroverseeraddress #LEAVE LABEL AS JELLYSEER BUT USE YOU OVERSEER URL AND API
JELLYSEERR_API_KEY=jellyseeorOrOverseerkey

RADARR_URL=http://radarraddress
RADARR_API_KEY=radarrkey

TMDB_API_KEY=reallylongkey

```
Docker Compose
```
version: '3.8'
services:
  ocdarr:
    image: vansmak/ocdarr:amd64_dev
    environment:
      - SONARR_URL=${SONARR_URL}
      - SONARR_API_KEY=${SONARR_API_KEY}
      - JELLYSEERR_URL=${JELLYSEERR_URL}
      - JELLYSEERR_API_KEY=${JELLYSEERR_API_KEY}
      - RADARR_URL=${RADARR_URL}
      - RADARR_API_KEY=${RADARR_API_KEY}
      - TMDB_API_KEY=${TMDB_API_KEYL}
      - CONFIG_PATH=/app/config/config.json
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config
      - ./temp:/app/temp
    ports:
      - "5001:5001"
    restart: unless-stopped
```
📝 Rules System
Create rules using the OCDarr website (start with Default rule)
Rules define how OCDarr manages each show. Each rule has four components:

Get Option (get_option):  //breaking changes, labels are different than main branch, edit your config.json to match

    1 - Get only the next episode
    3 - Get next three episodes
    season - Get full seasons
    all - Get everything upcoming


Action Option (action_option):

    monitor - Only monitor episodes
    search - Monitor and actively search


Keep Watched (keep_watched):

    1 - Keep only last watched episode
    2 - Keep the last 2, etc
    season - Keep current season
    all - Keep everything


Monitor Watched (monitor_watched):

    true - Keep watched episodes monitored
    false - Unmonitor after watching



Rule Assignment
Shows can get rules in two ways:

Default Rule: Applied if no other rule matches
  This is the first rule you should edit to how you want most shows added as it will be applied if no other rule is 
  for example my Default rule is 
   ```
    "rules": {
        "Default": {
            "get_option": "1",
            "action_option": "search",
            "keep_watched": "1",
            "monitor_watched": true,
   ```
Manual Assignment: Through OCDarr's web interface
Automatic via Tags: When requesting shows through Overseerr/Jellyseerr if you dont add a tag then it will goto default.  
  If you use the "episodes" tag it will apply no rule and present you a form to select episodes you want, this is intended for individual episodes
## 🔗 Media Server Integration

### Plex (via Tautulli) Setup

1. In Tautulli, go to Settings > Notification Agents
2. Click "Add a new notification agent" and select "Webhook"
3. Configure the webhook:
   - **Webhook URL**: `http://your-ocdarr-ip:5001/webhook`
   - **Trigger**: Episode Watched
   - **JSON Data**: Use exactly this template:

![webhook](https://github.com/Vansmak/OCDarr/assets/16037573/cf0db503-d730-4a9c-b83e-2d21a3430ece)![webhook2](https://github.com/Vansmak/OCDarr/assets/16037573/45be66c2-1869-49c1-8074-9081ed7c913b)
![webhook3](https://github.com/Vansmak/OCDarr/assets/16037573/24f02a75-2100-4b2a-9137-ce1e68803d1f)![webhook4](https://github.com/Vansmak/OCDarr/assets/16037573/f82198fc-e4c4-40ec-a9c7-551b2d8cdccd)

   ```json
   {
     "plex_title": "{show_name}",
     "plex_season_num": "{season_num}",
     "plex_ep_num": "{episode_num}"
   }
```
Important: Adjust your "Watched Percentage" in Tautulli's general settings to control when webhooks trigger.

Jellyfin Setup # not ready yet

In Jellyfin, go to Dashboard > Webhooks
Add a new webhook:

URL: http://your-ocdarr-ip:5002/jellyfin-webhook
Notification Type: Select "Playback Progress"



No template needed - Jellyfin sends structured data automatically. OCDarr processes events when playback reaches 45-55% of the episode.

Jellyseerr/Overseerr Webhook Setup  # this is used with the episodes tag to cancel the request after its added to sonarr, because if not your seer app will keep trying to track it.
                                      if you want requests to stay in seer then dont use the episodes tage when requesting.  

    In Jellyseerr, go to Settings > Notifications
    Add a new webhook notification
    Set the webhook URL to http://yourocdarr:5002/seerr-webhook
    Enable notifications for "Request Approved"
    Save the webhook configuration

Sonarr Webhook Setup
*To enable more control of requests, like episodes

In Sonarr, go to Settings > Connect
Click the + button to add a new connection
Select "Webhook"
Configure:

URL: http://your-ocdarr-ip:5002/sonarr-webhook
Triggers: Enable "On Series Add"
Leave other settings at default

Sonarr delayed release profile - this byes time while the script unmonitors episodes so downloads don't start

    Settings - profiles - add delay profile
    add a riduculous time like 10519200 # this is just to prevent downloads, it wont dl anything less than 20 years old, its a failsafe
    choose episodes tag
    do not select bypass


## 📋 Episode Selection Flow

OCDarr supports multiple ways to request and manage TV shows:

### External Requests (via Jellyseerr/Overseerr)

When requesting shows through Jellyseerr:
- **With "episodes" tag**: Follows the episode selection flow:
  1. Show is sent to Sonarr
  2. All episodes are unmonitored
  3. Downloads are canceled
  4. A pending season selection request is created
  5. User selects episodes
  6. If only S01E01 is selected: Episodes tag is removed, show is added to default rule
  7. If multiple episodes: Episodes tag is kept, only selected episodes are monitored
  8. Original Jellyseerr request is canceled automatically

- **Without "episodes" tag**: Show is directly added to the default rule

### Internal Requests (via OCDarr)

When requesting shows through OCDarr's interface:
1. Show is added to Sonarr with episodes tag
2. All episodes are unmonitored
3. Downloads are canceled
4. A pending season selection request is created
5. User selects episodes
6. If only E01 is selected: Episodes tag is removed, show is added to default rule (handled by your default preferences) #meant to mimic pilot episode
7. If multiple episodes: Episodes tag is kept, only selected episodes are monitored

This system gives you precise control over exactly which episodes you want, while cleaning up appropriately after requests.
