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

## Make the enquiry forms work (one time)

1. Go to <https://web3forms.com>, enter `letstravel@sunbirdtours.lk` and get your free **Access Key** by email.
2. Put it in `content/settings.txt` on the `web3forms_key:` line.

Until then the forms ask visitors to email or WhatsApp you instead.

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
