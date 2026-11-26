# Sunbird Lanka Tours website

The website for **sunbirdtours.lk** — 33 pages, built from simple text files.
You edit the text files; GitHub turns them into the website automatically.

## Where things are

| To change… | Edit this file |
|---|---|
| Phone, email, address, social links, form key | `content/settings.txt` |
| The menu | `content/menu.txt` |
| A tour (text, itinerary, FAQ, photo) | `content/tours/<tour-name>.md` |
| A destination | `content/destinations/<place>.md` |
| A blog post | `content/posts/<date>-<title>.md` |
| Home, About, MICE, Contact and other pages | `content/pages/<page>.md` |
| Guest reviews | `content/testimonials.txt` |
| Partner logos | `content/partners.txt` |
| Vehicles for hire | `content/vehicles.txt` |
| Old web addresses → new pages | `content/redirects.txt` |
| Photos | `static/img/…` |
| Colours and layout | `static/css/site.css` |

## The admin panel (the easy way)

Everything in the table above, apart from colours and layout, can also be changed in the admin panel:
tours with their days and photos, destinations, photos, reviews, logos, vehicles, settings and blog posts.
Photos are shrunk automatically when you upload them, so the site stays fast.

Everyone signs in with their **own email and password** (the team is kept in the inquiry box on
Cloudflare, see below). The first account is made with the setup code; after that, add people on the
**Team** page. Nobody needs a GitHub key.

**On your own computer:**

```
python admin.py
```

The panel opens at <http://localhost:8090/admin/>. Saving writes straight into the files in this folder
and rebuilds the site at once, so you can check it at <http://localhost:8090/>. To put the changes online,
upload them to GitHub as usual (GitHub Desktop: **Commit**, then **Push**).

**On the live website**, at `sunbirdtours.lk/admin/` (or `sunbirdlankatours.github.io/Website/admin/` before the
domain switch). Saving goes through the inquiry box, which saves the change to GitHub with its own GitHub
key (the `GITHUB_TOKEN` secret, see below), and the website updates about a minute later.

The repository it saves to is `GITHUB_REPO` in `worker/wrangler.toml` (and `admin_repo:` in `content/settings.txt`).
If you also edit files on your computer, **pull** in GitHub Desktop before you start, so you have the
changes made in the panel.

## Editing on github.com

1. Open the file on github.com and click the ✏️ pencil.
2. Change the text and click **Commit changes**.
3. About a minute later the website is updated.

### How the text files work

Each page starts with a few settings between `---` lines (title, photo, short summary),
followed by the text:

```
## A heading
### A smaller heading
Normal paragraph text. **Bold words** and *italic words*.
- a bullet point
[Link text](/contact-us/)
[Button text](/contact-us/#plan){.btn}
![Photo description](/img/tours/photo.jpg)
~ A line in the handwritten script style
```

- Several photos on one line become a photo row.
- `{{testimonials}}`, `{{tours:bespoke}}`, `{{form}}` and similar lines insert ready-made blocks.
- `::: band` … `:::` makes a full-width section (`::: band mist` gives it a light blue background).

### Adding a tour

Copy an existing file in `content/tours/`, rename it (the file name becomes the web address,
e.g. `kandy-day-tour.md` → `sunbirdtours.lk/kandy-day-tour/`), change the text and photo,
and add it to `content/menu.txt` if it should appear in the menu.

### Adding a photo

On github.com open `static/img/tours` (or another folder) → **Add file → Upload files**.
Use JPG photos around 1600 px wide or smaller. Then use `/img/tours/your-photo.jpg` in the text.

## Where trip letters and forms go

A letter or form sent from the website goes two ways at once. Either one arriving is enough:

- **Into the admin panel** (Inquiries), through the inquiry box on Cloudflare (next section).
- **By email** through Web3Forms. Go to <https://web3forms.com>, enter `letstravel@sunbirdtours.lk`,
  get the free **Access Key** by email and put it in `content/settings.txt` on the `web3forms_key:` line.

With neither, the forms ask visitors to email or WhatsApp you instead.

## The inquiry box on Cloudflare (one time)

The inquiry box is a small Cloudflare Worker (the `worker/` folder). It keeps the letters, and the
team's emails and passwords, in a free D1 database. The website itself can be hosted anywhere
(GitHub Pages now, Hostinger later): it only needs the inquiry box's address. Free, no card needed.

1. **Storage & Databases → D1 SQL Database → Create**, name it `sunbird-inquiries`.
2. **Workers & Pages → Create → Start with Hello World**, give it a name and **Deploy**. Note its
   address, ending in `.workers.dev`.
3. Open the Worker → **Bindings → Add binding → D1 database**: variable name `DB`,
   database `sunbird-inquiries` (tick **Use production value** for previews) → **Add Binding**.
4. Open the Worker → **Settings → Variables and Secrets → Add**: type **Secret**, name `SETUP_CODE`,
   and a value only you know (8 characters or more). It is used to make the first account, and
   to set a new password when one is forgotten.
5. A GitHub key for saving the website: on github.com (the account that owns the repository) open
   **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
   Repository access: **Only select repositories** → `Website`. Repository permissions:
   **Contents: Read and write** and **Actions: Read-only**. Copy it, and add it to the Worker like the
   setup code: type **Secret**, name `GITHUB_TOKEN`. When it runs out, make a new one the same way.
6. Put the Worker's address in `content/settings.txt` on the `inquiry_api:` line.
7. Send the code to the Worker (from the `worker` folder, on a computer with Node.js 22 or newer):
   `npx wrangler login` once, then `npx wrangler deploy`. The first time, put the database's id
   (Cloudflare shows it on the D1 page, or `npx wrangler d1 list`) in `worker/wrangler.toml`.
8. Open the admin panel → **First time, or forgot your password?**, type the setup code,
   your name, email and a password. Then add the rest of the team on the **Team** page.

How it works:

- Anyone can send a letter; only someone signed in can read them. The tables make themselves on first use.
- Signed-in team members can read and save the website's texts and photos (`content/` and `static/img/`)
  through it; it can't change anything else. Each save is one commit, with that person as its author.
- It takes letters only from the site's own addresses (`sunbirdtours.lk`, the GitHub test site and
  `localhost`); more can be added as `ALLOWED_ORIGINS` in the Worker's settings.
- At most 10 letters an hour from one connection. After 8 wrong passwords in 15 minutes, that
  connection has to wait 15 minutes.
- Passwords are kept scrambled (PBKDF2), never as typed. A sign-in lasts 30 days on a device.
- Changing a password signs out that person's other devices. Removing someone signs them out at once.

Photos: when Pillow is installed (`pip install pillow`),
the build makes smaller WebP copies of every photo in `/imgv/`, in several widths for the big ones,
so phones download phone-sized photos. The text files keep using the normal `/img/...jpg` names.

## The live chat

The chat card on every page (the sun in the corner, `chat_box: on` in `content/settings.txt`) is live
when `inquiry_api:` is set: travellers' messages go to the inquiry box, the team's phones ring, and the
team answers in the SunBird app (Android, `team-app/`). The code is `worker/src/chat.js`, `desk.js` and
`ring.js`, and the card's side is in `static/js/site.js`. Trip letters and enquiry forms show in the app too:
a new one gives every team phone a notification, and the number on the app icon counts those still marked New.

- **A traveller writes.** First they give their name and an email or WhatsApp number (the chat
  server refuses a new chat without them). The first message starts the chat. Their browser keeps the
  chat's key for 7 days, so an answer that comes later still shows when they come back.
- **The phones ring like a call.** A new chat rings every team phone, with a full call screen, until
  someone picks it up. More messages
  before anyone answers give a short ding; once someone answers, only their phone dings. Opening or
  answering a chat stops the other phones ringing. Only "ring, chat 12" goes through Google
  (Firebase); the words stay in our own database.
- **Answers arrive at once** on a live line (the "doorbell", a Cloudflare Durable Object). If a live
  line can't open, the card asks for news every 4 seconds while it is open.
- **Nobody in?** Outside office hours (`hours:` in settings), or when nobody has answered after
  3 minutes, the card says the answer will also reach their email or WhatsApp.
- **Limits:** 1,000 characters a message; 3 new chats an hour from one connection (60 from everyone);
  40 messages in 10 minutes in one chat. Only the site's own addresses can use it. Chats are deleted
  a year after their last message.

To switch the ringing on (once): in the Firebase console, make a project (Analytics off) and add an
Android app to it. Then **Project settings → Service accounts → Generate new private key**, and add
the whole downloaded file's contents to the Worker as a secret called `FCM_SERVICE_ACCOUNT`, the same
way as `SETUP_CODE`. Never put that file in this folder or on GitHub. The doorbell needs a deploy with
wrangler (`npx wrangler deploy` in `worker`); the Cloudflare dashboard's Edit code can't add it.

## Publish on Cloudflare Pages (one time)

Every push builds the site on GitHub (`.github/workflows/publish.yml`) and sends it to Cloudflare Pages.
A push to `main` goes live; a push to any other branch gets its own preview address.

1. **Cloudflare key:** dash.cloudflare.com → your profile → **API Tokens → Create Token → Custom token**,
   permission **Account → Cloudflare Pages → Edit**, for your account. Copy the token.
2. **Account ID:** shown on the Cloudflare dashboard home (Account details), or in the address bar.
3. **GitHub:** the repository → **Settings → Secrets and variables → Actions → New repository secret**:
   `CLOUDFLARE_API_TOKEN` (the token) and `CLOUDFLARE_ACCOUNT_ID` (the ID).
4. Push anything (or **Actions → Publish website → Run workflow**). The first run makes the Cloudflare
   project `sunbirdtours` and puts the site at its `….pages.dev` address (kept out of Google by `static/_headers`).
5. **Go live:** Cloudflare → **Workers & Pages → sunbirdtours → Custom domains** → add `sunbirdtours.lk`
   (and `www.sunbirdtours.lk`). Cloudflare points the domain at the site itself.
   **Don't touch the MX / email records.**

The build also writes `_redirects`, so the old WordPress addresses answer with a real 301.

The site went live this way on 2026-11-26. The old GitHub Pages test address
(`sunbirdlankatours.github.io/Website/`) is no longer published. `build.py` can still build for a sub-folder
with `SITE_BASE_PATH=/Website`, should a test address in a sub-folder ever be needed again.

## Preview on your own computer (optional)

```
python build.py
python -m http.server 8000 --directory _site
```

Then open <http://localhost:8000>.

To try the inquiry box on your own computer, run it with `npx wrangler dev --var SETUP_CODE:try-it-out`
in the `worker` folder (it keeps its own test database), and build with
`INQUIRY_API=http://localhost:8787` so the site and the admin panel use it.
