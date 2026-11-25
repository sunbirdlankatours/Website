# Sunbird Team (the team's Android app)

The phone rings when a traveller starts a chat on the website, and the team answers here. It signs in with the
same email and password as the admin panel. The chats live in the inquiry box (`worker/` in the website's
folder); Firebase is only used to wake the phone, and only "ring, chat 12" goes through it, never the words.

What it does:

- **Chats:** open chats, newest first, with how many messages are waiting, the traveller's country and the
  page they're writing from. Closed chats are under **Closed**.
- **A chat:** the messages, a reply box (your first name is shown to the traveller), "typing…" both ways, and
  buttons to email or WhatsApp the traveller if they left an address. Close, open again, or delete it.
- **Ringing:** a new chat rings like a phone call until someone looks; after two minutes it turns into a
  quiet reminder. More messages give a short sound. When someone opens or answers a chat, the other phones
  stop ringing for it. Each sound can be changed in Android's settings (menu → **Ring sound**).

## Putting it on a phone

1. Send `apk/Sunbird-Team.apk` to the phone (WhatsApp it to yourself, Google Drive, or a USB cable).
2. Open it on the phone. Android asks to allow installs from that app (WhatsApp, Files, Chrome…): allow it.
3. Google Play Protect may say it doesn't recognise the app, because it isn't from the Play Store. Choose
   **More details → Install anyway**.
4. Open **Sunbird Team** and sign in with your admin panel email and password.
5. Allow notifications when asked.
6. Menu (three dots) → **Send a test ring**. It should ring.

A new version installs over the old one the same way (it must be signed with the same key, see below).

### Phones that pause apps

Some makers delay rings to save battery. If rings come late or not at all:

- **Samsung:** Settings → Battery → Background usage limits → Never sleeping apps → add Sunbird Team.
- **Xiaomi / Redmi / POCO:** Settings → Apps → Sunbird Team → Autostart on; Battery saver → No restrictions.
- **Oppo / Realme / Vivo:** Settings → Battery → Sunbird Team → Allow background activity.

## Switching the rings on (once)

1. Go to [console.firebase.google.com](https://console.firebase.google.com) and **Create a project** called
   `Sunbird Team`. Turn **Google Analytics off**.
2. In the project, click the **Android** icon to add an app. Package name: `lk.sunbirdtours.team`.
   Nickname: `Sunbird Team`. **Register app**.
3. **Download google-services.json** and put it in this folder's `app/` folder (next to `build.gradle.kts`).
   Skip the rest of Firebase's steps (Next, Next, Continue to console). It is kept off GitHub.
4. **Project settings** (the gear) → **Service accounts** → **Generate new private key**. In Cloudflare, open
   the inquiry box Worker → **Settings → Variables and Secrets → Add**: type **Secret**, name
   `FCM_SERVICE_ACCOUNT`, and paste the whole downloaded file as the value. Then delete the downloaded file:
   never put it in this folder or on GitHub.
5. Build the app again (below). Its banner "can't ring yet" goes away.

## Building it (on this computer)

Double-click `build-apk.cmd`. It makes `apk/Sunbird-Team.apk`, signed with the key in `keystore/`.

- **The signing key** (`keystore/` and `keystore.properties`) is kept off GitHub. Back them up: without them, a
  new version can't be installed over the old one, and everyone would have to remove the app and install it
  again.
- It needs Java 21 (`%USERPROFILE%\.jdks\jdk-21.0.13+9`) and the Android SDK (`%LOCALAPPDATA%\Android\Sdk`),
  as set in `build-apk.cmd`. Change the version in `app/build.gradle.kts` (`versionCode` up by one, and
  `versionName`) for each new version.
- To try it against an inquiry box running on this computer (`npx wrangler dev` in `worker`, from the
  emulator): `gradlew assembleDebug -Psunbird.api=http://10.0.2.2:8787`. Test builds can pretend a ring
  arrived: `adb shell am broadcast -a lk.sunbirdtours.team.DEBUG_RING -n lk.sunbirdtours.team/.ring.DebugRingReceiver --es kind ring --el chat 5`.

The code: `data/` talks to the inquiry box (`Api.kt`) and keeps the live line open while the app is on screen
(`Live.kt`); `ring/` shows the rings; `ui/` is the screens (Jetpack Compose).
