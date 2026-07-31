"""Build RECUT_SPECS JSON for the 20 HP work-only reels (15-25s incl. 3s outro)."""
import json

TAGS = ("#fyp #ForYouPage #Trending #LandscapingTok #WorkHardPlayHard "
        "#BeforeAndAfter #Timelapse #Craftsmanship #BuildIt #ServiceBusiness "
        "#ContractorLife #OutdoorLiving #backyardgoals #TXOutdoorLiving #DreamBackyard "
        "#CollegeStation #Bryan #Navasota #Houston")
CTA = "Call (979) 701-2229!!"
GREEN = "0x35C935"


def cap(hook):
    return f"{hook}\n\n{CTA}\n•\n•\n{TAGS}"


def texts(line1, line2):
    return [
        {"text": line1, "start": 0.4, "end": 3.6, "color": GREEN, "border": True, "y": 0.40},
        {"text": line2, "start": 1.4, "end": 4.8, "y": 0.47},
    ]


def clip(name, parts, l1, l2, hook):
    """parts: list of (video, start, end)."""
    return {
        "name": name,
        "parts": [{"video": v, "start": a, "end": b} for v, a, b in parts],
        "mute": True,
        "outro": True,
        "texts": texts(l1, l2),
        "caption": cap(hook),
    }


BATCH1 = [
    clip("pool-reveal-overhead", [("DJI_0080", 0.5, 15.5)],
         "Backyard Or Resort?", "You Decide.",
         "Straight down on a backyard that doesn’t look real. 💧"),
    clip("freeform-pool-pullback", [("DJI_0081", 0.5, 10.5), ("DJI_0080", 2, 9)],
         "Built For Texas Summers", "Pools By HP.",
         "Built for Texas summers — and every one after. 🔥💧"),
    clip("modern-pool-spa", [("DJI_0059", 1, 8), ("DJI_0059", 10, 17), ("DJI_0059", 19, 25)],
         "Clean Lines. Blue Water.", "Luxury, Delivered.",
         "Clean lines, blue water, zero shortcuts. ✨"),
    clip("pool-firepit-luxe", [("DJI_0061", 0.5, 11.5), ("DJI_0080", 3, 10)],
         "Fire And Water", "One Backyard.",
         "Fire and water in the same backyard. That’s the standard. 🔥💧"),
    clip("lakefront-estate", [("DJI_0042", 1, 8), ("DJI_0042", 10, 17), ("DJI_0042", 19, 26)],
         "Lakefront Living", "Done Right.",
         "Lakefront living, done the right way. 🌿"),
    clip("pool-from-above", [("DJI_0078", 1, 8), ("DJI_0078", 10, 17), ("DJI_0078", 18, 25)],
         "Every Angle Earned", "HP Landscaping",
         "Every angle of this one was earned. 💯"),
    clip("estate-putting-green", [("DJI_0070", 2, 9), ("DJI_0070", 12, 19), ("DJI_0070", 22, 28)],
         "Your Own Front Nine", "Steps From The Door.",
         "Your own front nine, steps from the back door. ⛳🌱"),
    clip("ranch-estate-lawn", [("DJI_0071", 3, 10), ("DJI_0071", 20, 27), ("DJI_0071", 40, 46)],
         "Room To Breathe", "Texas Sized.",
         "Room to breathe — Texas sized. 🌿"),
    clip("curb-appeal-aerial", [("DJI_0074", 2, 9), ("DJI_0074", 15, 22), ("DJI_0074", 30, 37)],
         "Curb Appeal That Lasts", "From The Ground Up.",
         "Curb appeal that still looks like this in five years. 🌱"),
    clip("brick-estate", [("DJI_0077", 1, 8), ("DJI_0077", 9, 17)],
         "First Impressions Matter", "We Build Them.",
         "First impressions matter. We build them. ✨"),
]

BATCH2 = [
    clip("crew-on-site", [("DJI_0076", 0.5, 8), ("DJI_0075", 2, 10)],
         "Show Up. Work Hard.", "Every Single Day.",
         "Show up, work hard, leave it better than we found it. 💪"),
    clip("big-lot-transformation", [("DJI_0082", 2, 9), ("DJI_0082", 15, 22), ("DJI_0082", 28, 35)],
         "Big Lot, Bigger Vision", "HP Landscaping",
         "Big lot. Bigger vision. 🌿"),
    clip("country-estate-pond", [("DJI_0082", 10, 17), ("DJI_0077", 2, 9), ("DJI_0082", 30, 37)],
         "Country Living", "Elevated.",
         "Country living, elevated. 🌾✨"),
    clip("resort-courtyard-pool", [("DJI_0095", 1, 8), ("DJI_0095", 9, 16), ("DJI_0095", 17, 24)],
         "Resort Living", "At Home.",
         "Resort living without leaving home. 💧"),
    clip("rooftop-pool-city", [("DJI_0097", 0.5, 6.5), ("Rooftop", 20, 28), ("Rooftop", 40, 47)],
         "Commercial Grade", "Same Standard.",
         "Commercial jobs, same standard as your backyard. 💯"),
    clip("sunset-rooftop", [("Rooftop", 2, 9), ("Rooftop", 12, 19), ("Rooftop", 30, 37)],
         "Golden Hour", "Above It All.",
         "Golden hour hits different up here. 🌅"),
    clip("aggieland-pride", [("DJI_0086", 0.5, 9.5), ("DJI_0095", 5, 13)],
         "Built In Aggieland", "Serving All Of Texas.",
         "Built in Aggieland, serving all of Texas. 📍"),
    clip("poolside-details", [("MVI_3698", 0.3, 4.5), ("DJI_0061", 1, 8), ("DJI_0080", 4, 11)],
         "It’s In The Details", "Always.",
         "It’s always in the details. ✨"),
    clip("pergola-shade", [("DJI_0083", 0.2, 3.8), ("DJI_0070", 15, 23), ("DJI_0071", 12, 19)],
         "Shade Where You Want It", "Style Everywhere Else.",
         "Shade where you want it. Style everywhere else. 🌿"),
    clip("texas-built-different", [("DJI_0059", 2, 9), ("DJI_0042", 12, 19), ("DJI_0080", 3, 10)],
         "Texas Built Different", "HP Landscaping",
         "Texas built different. 💯🌿"),
]

if __name__ == "__main__":
    import sys
    batch = BATCH1 if sys.argv[1] == "1" else BATCH2
    out = json.dumps(batch, ensure_ascii=False, separators=(",", ":"))
    print(out)
    sys.stderr.write(f"{len(batch)} specs, {len(out)} chars\n")
    for c in batch:
        body = sum(p["end"] - p["start"] for p in c["parts"]) - 0.4 * (len(c["parts"]) - 1)
        sys.stderr.write(f"  {c['name']:<26} body {body:5.1f}s  total {body + 3:5.1f}s\n")
