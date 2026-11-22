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

**On your own computer:**

```
python admin.py
```

The panel opens at <http://localhost:8090/admin/>. Saving writes straight into the files in this folder
and rebuilds the site at once, so you can check it at <http://localhost:8090/>. To put the changes online,
upload them to GitHub as usual (GitHub Desktop: **Commit**, then **Push**).

**On the live website**, at `sunbirdtours.lk/admin/` (or `vockshel-gif.github.io/SunBird/admin/` before the
domain switch). Saving sends the change to GitHub, and the website updates about a minute later. The first
time, the panel asks for a GitHub key:

1. On github.com open **Settings → Developer settings → Fine-grained tokens → Generate new token**.
2. Repository access: **Only select repositories** → this website's repository.
3. Repository permissions: **Contents: Read and write** (and **Actions: Read-only** to see when the site is live).
4. Copy the token and paste it into the panel. It stays in that browser only. Don't share it.

The repository the panel saves to is set by `admin_repo:` in `content/settings.txt`.
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

- **Into the admin panel** (Inquiries). This works once the site runs on Cloudflare Pages
  with the inquiry box connected (next section).
- **By email** through Web3Forms. Go to <https://web3forms.com>, enter `letstravel@sunbirdtours.lk`,
  get the free **Access Key** by email and put it in `content/settings.txt` on the `web3forms_key:` line.

With neither, the forms ask visitors to email or WhatsApp you instead.

## Host on Cloudflare Pages, with the inquiry box (one time)

Cloudflare builds the site straight from this GitHub repository (it doesn't need GitHub Actions),
serves it fast all over the world, and keeps the inquiries in a free D1 database.
Use the Cloudflare account that already holds the `sunbirdtours.lk` DNS.

1. **Workers & Pages → Create → Pages → Connect to Git**, allow Cloudflare to see the `SunBird`
   repository and pick it.
2. Build settings: framework preset **None**, build command
   `pip install -r requirements.txt && python build.py`, build output directory `_site`,
   production branch `main`. **Save and Deploy.**
   The site appears at `https://<project-name>.pages.dev`.
3. **Workers & Pages → D1 SQL database → Create**, name it `sunbird-inquiries`.
4. Open the Pages project → **Settings → Bindings → Add → D1 database**:
   variable name `DB`, database `sunbird-inquiries` → Save.
5. **Deployments → the newest one → ⋯ → Retry deployment**, so the site picks up the database.
6. Test it: send a letter from `https://<project-name>.pages.dev/contact-us/`, then open
   `https://<project-name>.pages.dev/admin/`, sign in with the GitHub key and open **Inquiries**.

How it works:

- The inquiry box is `functions/api/inquiries.js`. The table makes itself on first use.
- It lets in whoever signs in to the admin panel with a GitHub key that may change this repository.
- It takes at most 10 letters an hour from one connection.
- Every save in the admin panel starts a new Cloudflare build. The top bar says "Live on the site"
  when it's done. The free plan allows 500 builds a month.
- **Moving the real domain** (only when you're ready to replace the old WordPress site): in the Pages
  project, open **Custom domains → Set up a custom domain** and add `sunbirdtours.lk`, then `www.sunbirdtours.lk`.
  **Do not change the MX / email records.**
- Once Cloudflare hosts the site, `.github/workflows/publish.yml` (GitHub Pages) isn't needed any more.

Photos: when Pillow is installed (`pip install pillow`; on Cloudflare the build command installs it),
the build makes smaller WebP copies of every photo in `/imgv/`, in several widths for the big ones,
so phones download phone-sized photos. The text files keep using the normal `/img/...jpg` names.

## Publish on GitHub Pages (one time)

1. Create a new repository on github.com (for example `sunbirdtours-website`) and upload this folder
   (GitHub Desktop: **File → Add local repository → Publish repository**).
2. On github.com: **Settings → Pages → Source: GitHub Actions**.
3. **Settings → Pages → Custom domain:** `sunbirdtours.lk` → Save.
4. Point the domain to GitHub (Cloudflare DNS, all "DNS only"):
   - four `A` records for `sunbirdtours.lk`: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - `CNAME` record `www` → `<your-github-username>.github.io`
   - **Do not change the MX / email records.**
5. When GitHub shows the certificate is ready, tick **Enforce HTTPS**.

### Test address before the domain switch

Until step 3 is done, the site runs at `https://vockshel-gif.github.io/SunBird/`.
The build adjusts every link for that sub-folder automatically, and stops doing so
as soon as the custom domain is set. Nothing needs changing by hand.

## Preview on your own computer (optional)

```
python build.py
python -m http.server 8000 --directory _site
```

Then open <http://localhost:8000>.

To try the inquiry box on your own computer, build with `INQUIRY_API=/api/inquiries` (or `CF_PAGES=1`)
and serve `_site` with Cloudflare's `wrangler pages dev _site --d1 DB` instead.
