# SunBird (the team's Android app)

The phone rings when a traveller starts a chat on the website, and the team answers here. Trip letters and
enquiry forms from the website show here too, with a notification and a number on the app icon. It signs in
with the same email and password as the admin panel. The chats and inquiries live in the inquiry box
(`worker/` in the website's folder); Firebase is only used to wake the phone, and only "ring, chat 12" or
"inquiry 7" goes through it, never the words.

What it does:

- **Chats:** open chats, newest first, with how many messages are waiting, the traveller's country and the
  page they're writing from. Closed chats are under **Closed**.
- **A chat:** the messages, a reply box (your first name is shown to the traveller), "typing…" both ways, and
  buttons to email or WhatsApp the traveller if they left an address. Close, open again, or delete it.
- **Ringing like a call:** a new chat rings like a phone call. A locked or sleeping phone wakes up to the call
  screen (the traveller's name, country, email or WhatsApp, their message and the page they're on); a phone
  in use shows Android's call banner with **Answer** and **Decline**; with the app open, the call screen
  appears inside it. On the call screen, **swipe the yellow bubble up** to open the chat (a tap only makes
  it hop, so a pocket can't answer). If the phone has a PIN, pattern or fingerprint lock, Android asks for
  it first, so travellers' details stay private; with a plain swipe lock it goes straight in. **Later** (or
  Decline) stops only your phone; the others keep ringing, and after two minutes the ring turns into a quiet
  reminder. When someone opens or answers a chat, the other phones stop ringing and their call screens close.
  More messages give a short sound. Each sound can be changed in Android's settings (menu → **Ring sound**).
- **Inquiries** (the tab at the bottom): trip letters and enquiry forms from the website, newest first, with
  New / Replied / Booked / Closed like the admin panel. Open one for everything they sent, **Email**,
  **WhatsApp** and **Call** buttons, its status and a team note (both show in the admin panel too). Deleting
  stays in the admin panel. A new inquiry gives every team phone a notification, and the number on the app icon
  (and on the tab) counts the inquiries still marked **New**; it goes down when anyone marks one. Chats don't
  count on the icon. Most phones show the number; some only show a dot.
- **Set up this phone:** a yellow card at the top lists what the phone still needs so SunBird rings even when
  it's closed (notifications, running in the background, auto-start on phones like ZTE or Xiaomi, full-screen
  calls, the ring sound), each with a button to the right Android page. **Test with the app closed** sends a
  test ring 20 seconds later: swipe SunBird away and lock the phone, and it should still ring.
- **Opening the app:** the logo's emblem builds itself (only the round symbol: no motto, no words). Coming in
  from a ring, or opening the app while a chat is ringing, skips that and goes straight to the chat.

## Putting it on a phone

1. Send `apk/SunBird.apk` to the phone (WhatsApp it to yourself, Google Drive, or a USB cable).
2. Open it on the phone. Android asks to allow installs from that app (WhatsApp, Files, Chrome…): allow it.
3. Google Play Protect may say it doesn't recognise the app, because it isn't from the Play Store. Choose
   **More details → Install anyway**.
4. Open **SunBird** and sign in with your admin panel email and password.
5. Allow notifications when asked, then go down the yellow **Set up this phone** card until it disappears.
6. Tap **Test with the app closed**, swipe SunBird away from the recent apps and lock the phone. Within
   20 seconds the call screen should appear and ring.

A new version installs over the old one the same way (it must be signed with the same key, see below).

### Phones that pause apps

Many makers (ZTE, Xiaomi, Oppo, Vivo, Tecno…) stop an app completely when it is swiped away from the recent
apps, and then nothing can ring it until it is opened again. Famous apps like WhatsApp are on the maker's own
list; SunBird has to be allowed once, by hand. The **Set up this phone** card does most of it. If rings still
don't come with the app closed, compare SunBird's settings with WhatsApp's (Settings → Apps → WhatsApp, then
SunBird) and switch on the same battery, auto-start and background settings. Also:

- **Samsung:** Settings → Battery → Background usage limits → Never sleeping apps → add SunBird.
- **Xiaomi / Redmi / POCO:** Settings → Apps → SunBird → Autostart on; Battery saver → No restrictions.
- **Oppo / Realme / Vivo:** Settings → Battery → SunBird → Allow background activity.
- If the phone lets you lock an app in the recent apps (long-press its card), lock SunBird.

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

Double-click `build-apk.cmd`. It makes `apk/SunBird.apk`, signed with the key in `keystore/`.

- **The signing key** (`keystore/` and `keystore.properties`) is kept off GitHub. Back them up: without them, a
  new version can't be installed over the old one, and everyone would have to remove the app and install it
  again.
- It needs Java 21 (`%USERPROFILE%\.jdks\jdk-21.0.13+9`) and the Android SDK (`%LOCALAPPDATA%\Android\Sdk`),
  as set in `build-apk.cmd`. Change the version in `app/build.gradle.kts` (`versionCode` up by one, and
  `versionName`) for each new version.
- To try it against an inquiry box running on this computer (`npx wrangler dev` in `worker`, from the
  emulator): `gradlew assembleDebug -Psunbird.api=http://10.0.2.2:8787`. Test builds can pretend a ring
  arrived: `adb shell am broadcast -a lk.sunbirdtours.team.DEBUG_RING -n lk.sunbirdtours.team/.ring.DebugRingReceiver --es kind ring --el chat 5`
  (`--es kind inquiry --el chat 7` for a new inquiry). `-Psunbird.autostart` shows the auto-start step on any
  phone, to try it on the emulator.

The code: `data/` talks to the inquiry box (`Api.kt`) and keeps the live line open while the app is on screen
(`Live.kt`); `ring/` shows the rings; `ui/` is the screens (Jetpack Compose).
