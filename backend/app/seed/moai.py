"""Moai (Redefined Vegetarian Dining, Jayanagar, Bengaluru) - drinks and smoothie bowls.

The food menu is in moai_food.py; the restaurant's menu lists food first.

Source: photographs of the restaurant's printed menu (October 2026). Names
and prices are as printed; obvious spelling slips were normalised ("Lytchi"
-> "Lychee", "Kafier" -> "Kaffir", "Amm" -> "Aam"). "Choice of flavours"
entries become options: the plain drink at its listed price, each flavour
at the listed price plus the printed "add flavour" charge.

Moai is a vegetarian restaurant (its menu says so on every page), so every
item is vegetarian. Vegan status, ingredients and allergens are NOT verified
and stay "unknown". Strength and sweetness are coarse estimates from the
drink type, used only for ranking. Photos are crops of the restaurant's own
menu photography; items without one show a neutral placeholder.

Left out: "Vietnamese-Style Cold Coffee" - its price is cut off in the photo.
"""

from decimal import Decimal as D

from app.seed.data import item
from app.seed.moai_food import FOOD_CATEGORIES

IMG = "/r/moai/{}.jpg"

HOT_COFFEE = dict(type="beverage", temp="hot", coffee=True, veg=True, tags=["coffee"],
                  pairs=["chocolate", "nutty", "dates", "creamy"])
COLD_COFFEE = dict(type="beverage", temp="cold", coffee=True, veg=True, tags=["coffee", "cold brew"],
                   pairs=["chocolate", "nutty", "creamy"])
TEA = dict(type="beverage", temp="hot", coffee=False, veg=True, tags=["tea"], strength=None, sweet=1)
COLD = dict(type="beverage", temp="cold", coffee=False, veg=True)
MOCKTAIL = dict(COLD, tags=["mocktail", "signature"], sweet=3, pairs=["nutty", "creamy"])
SODA = dict(COLD, tags=["soda", "fizz"], sweet=2)
BOWL = dict(type="food", veg=True, coffee=False, tags=["smoothie bowl", "breakfast", "healthy"], sweet=3,
            pairs=["coffee", "tea"])


def M(name, price, desc=None, *, flavours=None, add=None, plain="Classic", photo=None, **kw):
    """One item. ``flavours`` + ``add``: options priced at base + add (add=None: same price)."""
    if flavours:
        base = D(price)
        extra = D(add) if add else D("0")
        opts = [(plain, base, True)] if plain else []
        opts += [(f, base + extra, not opts and i == 0) for i, f in enumerate(flavours)]
        kw["variants"] = opts
        kw.setdefault("variant_required", False)
    flavour_words = [f.lower() for f in flavours or []]
    kw.setdefault("flavors", [w for w in flavour_words if " " not in w][:6])
    return item(name, price, desc=desc, image=IMG.format(photo) if photo else None, **kw)


def cat(name, slug, description, items):
    return dict(name=name, slug=slug, description=description, items=items)


DRINK_CATEGORIES = [
    cat("A Cup of Joy", "cup-of-joy", "Milk coffees, hot chocolate and affogato.", [
        M("Cappuccino", "220", "A timeless Italian classic with a Moai twist. Bold espresso meets silky steamed milk, topped "
          "with a cloud of micro foam. Balanced, rich and satisfying.",
          flavours=["Cardamom", "Caramel", "Hazelnut", "Nutella"], add="40", photo="cappuccino", featured=True,
          strength=3, sweet=1, **HOT_COFFEE),
        M("Café Latte", "240", "Velvety, mellow and deeply comforting. Our house espresso with steamed milk for a creamy, "
          "balanced sip that hits the spot, any time of day.",
          flavours=["Café Mocha", "Vanilla", "Caramel", "Hazelnut", "Gingerbread"], add="40",
          strength=2, sweet=1, keywords=["latte"], **HOT_COFFEE),
        M("Hot Chocolate", "240", "A comforting classic, reimagined with intention. Real dark cocoa, lightly sweetened and "
          "blended with steamed milk to a silky-smooth finish. No syrup shortcuts here.",
          flavours=["Nutella", "Spiced"], type="beverage", temp="hot", coffee=False, veg=True, sweet=3,
          tags=["chocolate"], pairs=["dates", "nutty"]),
        M("Affogato", "210", "A decadent Italian treat: a scoop of vanilla ice cream drowned in freshly pulled espresso. "
          "Rich, creamy and bold.",
          flavours=["Dates", "Kulfi", "Pistachio", "Choco", "Berries"], add="30", plain="Vanilla",
          type="dessert", temp=None, coffee=True, veg=True, strength=3, sweet=4, tags=["coffee", "ice cream"]),
    ]),
    cat("Espresso", "espresso", "Short, strong and straight from the machine.", [
        M("Espresso", "140", "Pure, bold and concentrated shot.", photo="espresso", strength=5, sweet=1, **HOT_COFFEE),
        M("Americano", "170", "Espresso diluted with hot water.", strength=4, sweet=1, **HOT_COFFEE),
        M("Macchiato", "170", "A bold shot of espresso \"marked\" with just a dollop of steamed milk or foam.",
          strength=4, sweet=1, **HOT_COFFEE),
        M("Cortado", "180", "The milk softens the bold espresso without overpowering it. Perfect if you like your "
          "coffee strong but not too intense.", strength=4, sweet=1, **HOT_COFFEE),
    ]),
    cat("South Brew", "south-brew", "South Indian coffee, the traditional way.", [
        M("Filter Coffee", "90", "Bold and earthy from the chicory.", photo="filter-coffee", featured=True,
          strength=4, sweet=2, **HOT_COFFEE),
        M("Karupatti Coffee", "100", "Coffee sweetened with karupatti (palm jaggery), with or without milk.",
          flavours=["With milk", "Without milk"], plain=None, strength=4, sweet=3, **HOT_COFFEE),
    ]),
    cat("Moai Brew (Ritual Series)", "moai-brew", "Slow, hand-brewed coffee.", [
        M("V60", "200", "A slow-crafted pour-over using the iconic V60 dripper, delivering a clean cup with delicate "
          "flavour notes and balanced clarity.", strength=3, sweet=1, keywords=["pour over"], **HOT_COFFEE),
        M("French Press", "200", "Where immersion meets flavour: coarse grounds steeped in hot water, then pressed "
          "slowly to extract rich oils and deep notes.", photo="french-press", strength=4, sweet=1, **HOT_COFFEE),
    ]),
    cat("Tea", "tea", "Japanese tea rituals and calming green teas - grounded, serene, intentional.", [
        M("Green Tea", "120", "Light green tea with your choice of infusion.",
          flavours=["Mint", "Honey Lemon", "Holy Basil", "Kahwa", "Mint & Kahwa", "Honey Lemon & Holy Basil"],
          plain=None, **{**TEA, "tags": ["tea", "green tea"]}),
        M("Japanese Tea", "200", "Traditional Japanese tea, brewed with care.",
          flavours=["Sencha", "Matcha", "Genmaicha", "Gyokuro"], plain=None, **{**TEA, "tags": ["tea", "japanese tea"]}),
    ]),
    cat("Cold Brew & Iced Teas", "cold-brew-iced-tea", "Chilled teas and slow-steeped cold brew.", [
        M("Classic Iced Tea", "160", "Chilled iced tea, plain or with a flavour.",
          flavours=["Watermelon", "Peach", "Cranberry", "Mango", "Ginger", "Apple Spice", "Orange Spice", "Rose",
                    "Hibiscus", "Bubble Iced Tea"], add="20", sweet=2, tags=["tea", "iced tea"], **COLD),
        M("Classic Cold Brew", "180", "Slow-steeped cold brew coffee, plain or with a fruit flavour.",
          flavours=["Watermelon", "Orange", "Rosemary", "Passion Fruit", "Peach", "Blueberry"], add="40",
          featured=True, strength=4, sweet=1, **COLD_COFFEE),
        M("Café Bombón", "220", "A rich espresso layered with sweet condensed milk for a creamy Spanish delight.",
          strength=3, sweet=5, **{**COLD_COFFEE, "tags": ["coffee"]}),
    ]),
    cat("Milkshakes", "milkshakes", "Thick, indulgent shakes - several inspired by Indian sweets.", [
        M("Peda Milkshake", "260", "A classic mithai with a creamy, dreamy twist.", sweet=5, tags=["shake", "mithai"], **COLD),
        M("Snickers Milkshake", "260", "All your cravings blended into one sinful shake.", sweet=5,
          tags=["shake", "chocolate"], **COLD),
        M("Banana Cream Pie Milkshake", "260", "Like sipping sunshine off a dessert plate.", sweet=4,
          tags=["shake"], flavors=["banana"], **COLD),
        M("Dates Milkshake", "290", "The rich, caramel kiss of nature in a chilled swirl.", sweet=4,
          tags=["shake"], flavors=["dates", "caramel"], **COLD),
        M("Peanut Butter Milkshake", "280", "A thick, nutty hug for your taste buds.", sweet=4,
          tags=["shake"], flavors=["peanut", "nutty"], **COLD),
        M("Peanut Butter & Brownie Milkshake", "280", "Chunky, gooey and totally extra.", sweet=5,
          tags=["shake", "chocolate"], flavors=["peanut", "brownie", "chocolate"], **COLD),
        M("Kaju Katli Milkshake", "280", "Your favourite festive sweet, now in slurp form.", sweet=5,
          tags=["shake", "mithai"], flavors=["cashew", "nutty"], **COLD),
    ]),
    cat("Frappés", "frappes", "Blended iced coffee.", [
        M("Classic Frappé", "260", "Blended iced coffee, plain or with a flavour.",
          flavours=["Tiramisu", "Popcorn", "Salted Caramel", "Cherry & Vanilla", "Coconut & Blueberry", "Matcha",
                    "Caramel", "Hazelnut", "Chocolate"], add="30",
          strength=2, sweet=4, **{**COLD_COFFEE, "tags": ["coffee", "frappe", "blended"]}),
    ]),
    cat("Signature Mocktails", "mocktails", "Moai's theatrical, garden-fresh mocktails.", [
        M("Ahu Mystique", "320", "Dark berries meet garden herbs in this vibrant mocktail with sweet mulberry and a citrusy "
          "lift, crowned with a sharp, fizzy paneer soda pop.", photo="ahu-mystique", featured=True,
          flavors=["berry", "mulberry", "herbal", "citrus"], **MOCKTAIL),
        M("Moai Chancasa", "270", "Fresh sugarcane juice, mint, house-made ginger syrup, lemon and paneer soda (a fizzy "
          "Indian soda): sweet, spicy, tangy and fizzy in one go.", photo="moai-chancasa", featured=True,
          flavors=["sugarcane", "mint", "ginger", "lemon", "spicy"], **MOCKTAIL),
        M("Island Guardian", "320", "A tropical blend of litchi, lime, passion fruit, coconut syrup and cranberry, "
          "garnished with kaffir lime leaves.", photo="island-guardian", featured=True,
          flavors=["lychee", "passion fruit", "coconut", "cranberry", "tropical"], **MOCKTAIL),
        M("Blush & Burn", "270", "Grapefruit juice and tangy kokum syrup, spiked with a touch of fiery chilli sauce - "
          "the perfect balance of sweet, sour and spicy.", photo="blush-and-burn",
          flavors=["grapefruit", "kokum", "spicy", "tangy"], **MOCKTAIL),
        M("Tango Twist", "320", "A golden burst of tropical fruit, balanced with citrus tang and a warm, velvety finish.",
          photo="tango-twist", flavors=["tropical", "citrus"], **MOCKTAIL),
        M("Mystique", "270", "A rich, ruby-toned mocktail of sharp cranberry, soft lychee sweetness and a golden "
          "drizzle of saffron-infused caramel.", photo="mystique",
          flavors=["cranberry", "lychee", "saffron", "caramel"], **MOCKTAIL),
        M("Rapa Nui", "270", "A deep violet blackcurrant base brightened by peach and citrus, crowned with butterfly pea "
          "flower tea for a magical indigo layer and finished with a sparkling ginger ale lift.",
          flavors=["blackcurrant", "peach", "citrus", "ginger"], **MOCKTAIL),
        M("Hojase De Laural", "270", "A herbaceous, gently sweet mocktail that feels fresh from a forest garden, with the "
          "signature Moai treatment.", flavors=["herbal"], **{**MOCKTAIL, "sweet": 2}),
        M("Stonehead Spritz", "270", "Juicy lychee and dragon fruit with delicate rose, citrus sparkle and a cooling mint "
          "lift. Light, floral and oh-so-pretty.", flavors=["lychee", "dragon fruit", "rose", "mint", "floral"], **MOCKTAIL),
        M("Specific Breeze", "320", "Pineapple, mango, mint, lemon and blue pea tea - vibrant and refreshing.",
          flavors=["pineapple", "mango", "mint", "lemon", "tropical"], **MOCKTAIL),
    ]),
    cat("Lassi & Buttermilk", "lassi-buttermilk", "Traditional cultured-milk coolers.", [
        M("Spiced Butter Milk", "170", "A tangy, refreshing cultured milk with a smooth texture and subtle acidity. "
          "Lovely on its own or alongside rich dishes.", sweet=1, tags=["buttermilk", "traditional"],
          flavors=["spiced", "tangy"], **COLD),
        M("Lassi", "220", "Thick, chilled yogurt lassi.", flavours=["Rabdi", "Mango"], plain=None, sweet=4,
          tags=["lassi", "traditional"], **COLD),
    ]),
    cat("Flavour Soda", "flavour-soda", "Sparkling house sodas.", [
        M(n, "199", desc, flavors=f, **SODA) for n, desc, f in [
            ("Spiced Jamun Fizz", "Jamun (Indian blackberry) soda with a hint of spice.", ["jamun", "spiced"]),
            ("Yuzu Fizz", "Bright, citrusy yuzu soda.", ["yuzu", "citrus"]),
            ("Kala Khatta Fizz", "The tangy-sweet street-style kala khatta, as a soda.", ["kala khatta", "tangy"]),
            ("Mint Blue Pea Fizz", "Mint and blue pea flower soda.", ["mint", "floral"]),
            ("Lychee Rose", "Lychee and rose soda.", ["lychee", "rose", "floral"]),
            ("Kachha Aam Panna", "Raw-mango aam panna, sparkling.", ["mango", "tangy"]),
            ("Mango Chilli", "Mango soda with a chilli kick.", ["mango", "spicy"]),
            ("Cucumber Kaffir Lime", "Cool cucumber with kaffir lime.", ["cucumber", "citrus"]),
        ]
    ]),
    cat("Smoothie Bowls", "smoothie-bowls", "Thick, spoonable bowls topped with fresh fruit, seeds and nuts.", [
        M("Tropinut", "400", "A creamy, protein-packed bowl of papaya, banana, Greek yogurt and peanut butter, lightly "
          "sweetened with honey and stirred with chia seeds. Topped with fresh fruit, seeds or nuts.",
          photo="tropinut", featured=True, flavors=["papaya", "banana", "peanut", "honey", "tropical"], **BOWL),
        M("Coco Lush", "350", "A tropical banana bowl blended with Greek yogurt, almond milk and honey, stirred with "
          "grated coconut and raisins. Topped with fresh fruit and crunchy dry fruits.",
          photo="coco-lush", flavors=["coconut", "banana", "honey"], **BOWL),
        M("Figgy Raisins Bliss", "450", "Soaked figs, raisins, almonds, Greek yogurt and honey, blended velvety with a "
          "splash of milk. Finished with fresh fruit slices and nuts.",
          photo="figgy-raisins-bliss", flavors=["fig", "raisin", "nutty", "honey"], **BOWL),
        M("Golden Glow Smoothie", "400", "Pineapple, mango, creamy peanut butter and ice cream blended into a luscious "
          "bowl, topped with fruit chunks and chocolate sauce.",
          photo="golden-glow-smoothie", flavors=["pineapple", "mango", "peanut", "chocolate"], **{**BOWL, "sweet": 4}),
        M("Berryshine Smoothie", "450", "Frozen bananas and strawberries with strawberry yogurt and honey, whipped into a "
          "silky bowl and finished with a juicy berry topping.",
          photo="berryshine-smoothie", flavors=["strawberry", "berry", "banana"], **BOWL),
    ]),
    cat("Quenchers", "quenchers", "Soft drinks, water and juice.", [
        M("Seasonal Fresh Juice", "150", "Freshly pressed juice of the season's fruit.", sweet=3, tags=["juice"], **COLD),
        M("Ginger Ale", "200", None, sweet=3, tags=["soft drink", "packaged"], **COLD),
        M("Diet Coke", "150", None, sweet=1, tags=["soft drink", "packaged"], caffeine="medium", **COLD),
        M("Red Bull", "250", None, sweet=4, tags=["energy drink", "packaged"], caffeine="high", **COLD),
        M("Alkaline Water", "90", None, sweet=1, tags=["water", "packaged"], **COLD),
    ]),
]

CATEGORIES = [*FOOD_CATEGORIES, *DRINK_CATEGORIES]

MOAI = {
    "restaurant": dict(
        slug="moai",
        name="Moai",
        tagline="Redefined · Vegetarian · Dining",
        address_line="Jayanagar",
        city="Bengaluru",
        phone=None,
        currency="INR",
    ),
    "settings": dict(
        assistant_name="Moai Guide",
        welcome_message=(
            "Welcome to Moai - redefined vegetarian dining, with no MSG, soda or artificial colours. Tell me what "
            "you're craving, who you're with and your budget, and I'll put together the perfect meal."
        ),
        suggested_prompts=[
            "What are your Moai specials?",
            "4 of us, starters and mains, budget ₹2500",
            "A spicy paneer starter",
            "Vegan mains",
            "Jain options",
            "Your most theatrical mocktail",
        ],
        brand_color="#223929",
        assistant_icon="utensils",
        ai_enabled=True,
        pickup_enabled=False,
        ordering_enabled=False,
        allergen_disclaimer=(
            "Everything at Moai is vegetarian. Vegan and allergen details haven't been verified - please check "
            "with staff if you have an allergy."
        ),
    ),
    "addons": [],
    "categories": CATEGORIES,
}
