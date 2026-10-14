"""Moai food menu, from the restaurant's PDF ("MOAI MAIN & JAIN V MENU").

Names, descriptions and prices are as printed (spelling slips normalised).
Markers from the PDF:
- "Moai Special" items are featured.
- The Vegan page marks items vegan. Two of them ("Ghee Dal Tadka", "Cream
  Cheese Dumpling") contradict their own names, so they stay "unknown" until
  the restaurant confirms.
- The Jain page becomes its own section; Jain dishes carry the "jain" tag.
Gluten-free icons can't be read reliably from the PDF and are not used.
Photos are the menu's own photography, one per captioned dish.
"""

from decimal import Decimal as D

from app.seed.data import item

IMG = "/r/moai/{}.jpg"

FLAVOUR_WORDS = [
    "spicy", "tangy", "creamy", "cheese", "cheesy", "garlic", "chilli", "smoky", "sweet", "butter", "ghee",
    "paneer", "mushroom", "corn", "broccoli", "burrata", "pesto", "mint", "coconut", "peanut", "cashew",
    "tomato", "spinach", "avocado", "mango", "pineapple", "chocolate", "rose", "saffron", "basil", "truffle",
    "podi", "thai", "schezwan", "kung pao", "tandoori", "mathania", "jaggery", "berry", "sumac", "lotus",
]

STARTER = ("starter",)
MAIN = ("main",)


def _flavours(name, desc):
    text = f"{name} {desc or ''}".lower()
    return [w for w in FLAVOUR_WORDS if w in text][:6]


def F(name, price, desc=None, *, tags=(), sizes=None, photo=None, special=False, vegan=None, kind="food", **kw):
    """One dish. ``sizes``: [(label, price)] - the first is the default."""
    if sizes:
        kw["variants"] = [(label, D(p), i == 0) for i, (label, p) in enumerate(sizes)]
        kw["variant_required"] = True
    return item(
        name, price, desc=desc, type=kind, veg=True, vegan=vegan, coffee=False, tags=list(tags),
        flavors=_flavours(name, desc), featured=special,
        # Rich, spiced food goes with bright, fizzy drinks (mocktails, sodas).
        pairs=kw.pop("pairs", ["mint", "lemon", "citrus", "ginger", "tangy", "lychee"] if kind == "food" else ["caramel", "nutty"]), image=IMG.format(photo) if photo else None, **kw,
    )


HALF_FULL = [("Half", "239"), ("Full", "309")]


def cat(name, slug, description, items):
    return dict(name=name, slug=slug, description=description, items=items)


FOOD_CATEGORIES = [
    cat("Recalling Soups", "soups", "Each spoonful blends flavours with playful twists - a taste of the past, reimagined.", [
        F("Classic Cream of Tomato Soup", "239", "A velvety tomato soup served with crunchy namak para.",
          tags=["soup", "jain-available"], sizes=HALF_FULL, photo="cream-of-tomato-soup"),
        F("Creamy Corn Soup", "239", "Sweet and savoury corn soup paired with tangy kurkure chaat.",
          tags=["soup", "jain-available"], sizes=HALF_FULL),
        F("Tom Yum Soup", "239", "Spicy Thai-style soup with a twist of noodles bhel.",
          tags=["soup"], sizes=HALF_FULL, vegan=True),
        F("Mountain Noodle Soup", "239", "Hearty bowl of noodles inspired by mountain flavours.",
          tags=["soup"], sizes=HALF_FULL, vegan=True),
        F("Manchow Soup", "239", "Bold and spicy soup served with crispy fried paneer wontons.",
          tags=["soup"], sizes=HALF_FULL),
    ]),
    cat("Harvested Salads", "salads", "Freshly harvested, crunchy and vibrant, with seasonal ingredients.", [
        F("Evergreen Gardenia Salad", "299", "Fresh green medley.", tags=["salad", "healthy", "jain-available"]),
        F("Turkish Shepherd's Salad", "349", "A zesty blend of veggies, sumac and yoghurt cream.",
          tags=["salad", "healthy", "jain-available"]),
        F("Cambodian Noodles Salad", "329", "Light and tangy noodle salad inspired by Southeast Asian street eats.",
          tags=["salad", "healthy"], vegan=True),
        F("Hall of Fame Caesar Salad", "329", "Our elevated version of the classic Caesar salad, served with parmesan flakes.",
          tags=["salad"]),
        F("Grilled Fruits & Burrata Salad", "389", "Grilled fruits paired with burrata, pesto cream and balsamic glaze.",
          tags=["salad", "jain-available"], photo="grilled-fruits-burrata-salad"),
    ]),
    cat("Artisanal Chaats", "chaats", "Handcrafted chaats reimagined with a gourmet touch.", [
        F("3 Way Dahi Aloo Tikki Chaat", "319", "Triple twist on the classic, drenched in creamy dahi.",
          tags=["chaat", *STARTER], photo="dahi-aloo-tikki-chaat"),
        F("Upside Down Basket Chaat", "369", "Basket chaat flipped with a flavourful filling and a tangy trio dip.",
          tags=["chaat", *STARTER]),
        F("Hare Patte Layer Chaat", "319", "Layered flavour bomb with Mathania chilli chutney and pineapple salsa.",
          tags=["chaat", *STARTER, "jain-available"], special=True),
        F("Creamy Avocado Chattak Puri", "399", "Crunchy puris loaded with avocado and tangy raw mango salsa.",
          tags=["chaat", *STARTER, "jain-available"]),
        F("Garlic Podi Masala Bhel", "319", "A fiery bhel uplifted with garlic podi magic.",
          tags=["chaat", *STARTER], vegan=True),
        F("Nadru Burrata Papdi Chaat", "429", "Lotus root fried chips and creamy burrata with sweet and tangy chutneys.",
          tags=["chaat", *STARTER], special=True),
    ]),
    cat("Mouthful Bites", "mouthful-bites", "Irresistibly shareable bites, crafted with passion.", [
        F("Chur Chur Papad", "289", "Crunchy, flaky papad with a burst of spicy, tangy flavours.",
          tags=["appetizer", *STARTER, "shareable"], vegan=True),
        F("Garlic Podi Dusted Baked Fries", "349", "Baked fries with spicy podi, served with tomato mint and Gouda dips.",
          tags=["appetizer", *STARTER, "shareable"]),
        F("Kalmi Vadi", "329", "Spiced vadi bites with Mathania chilli sauce, pineapple chutney and airy siphon dahi.",
          tags=["appetizer", *STARTER]),
        F("Podi Mushroom", "329", "Earthy mushrooms kissed with podi spice and dusted malto.",
          tags=["appetizer", *STARTER], photo="podi-mushroom"),
        F("Amaranth Coated Hara Bhara Kebab", "329", "Veggie-packed kebabs with a crunchy amaranth shell.",
          tags=["appetizer", *STARTER, "kebab"]),
        F("Aloo Cheese Khakhra Tostado", "369", "A crispy khakhra base topped with cheesy potato goodness.",
          tags=["appetizer", *STARTER]),
        F("Chole Kulcha Taco", "369", "Mini kulcha tacos loaded with masala chole and topped with mint cream.",
          tags=["appetizer", *STARTER]),
        F("Cottage Cheese Stuffed Pockets", "379", "Soft pockets bursting with a flavourful paneer filling.",
          tags=["appetizer", *STARTER, "jain-available"]),
        F("Edamame Galouti", "389", "Smooth edamame kebabs served on a hearty ragi disc.",
          tags=["appetizer", *STARTER, "kebab"], special=True, photo="edamame-galouti"),
        F("Tandoori Roasted Pineapple", "389", "Sweet pineapple roasted tandoori-style, served with soft chiffon malai.",
          tags=["appetizer", *STARTER, "jain-available"], special=True),
    ]),
    cat("Joy of Sharing", "joy-of-sharing", "Platters made for the table - togetherness on a plate.", [
        F("Curry Potato Buns", "429", "Soft buns stuffed with spiced potato curry and a kick of dry garlic chutney.",
          tags=["shareable", *STARTER], special=True),
        F("Clay Pot Veggie Platter", "1299", "Wholesome mix of veggies slow-cooked and served from a rustic clay pot.",
          tags=["shareable", "platter", *MAIN], special=True, serves=4),
        F("Baked Bhaji with 3 Types of Pav", "599", "Spicy bhaji served with Classic, Thecha and Sanchar pav and dry garlic chutney.",
          tags=["shareable", *MAIN], serves=2),
        F("Memory Lane Cheese Fondue", "799", "A nostalgic dip into molten cheese, perfect for sharing and reminiscing.",
          tags=["shareable", *STARTER], photo="cheese-fondue", serves=3),
        F("Mumbai Cheese Chutney Sandwich", "449", "Street-style sandwich layered with minty chutney and classic Mumbai flair.",
          tags=["sandwich", *MAIN]),
    ]),
    cat("Clay Pot & Tandoor", "clay-pot-tandoor", "Smoky tandoor and earthy clay pots - bold, tender flavours.", [
        F("Baked Peshawari Aloo", "379", "Stuffed potatoes marinated in a mix of spices and cooked in a tandoor.",
          tags=["tandoor", *STARTER]),
        F("Purani Delhi ke Soya Chaap", "369", "Stuffed cheesy soya chaap with creamy malai jhol.",
          tags=["tandoor", *STARTER, "jain-available"], special=True, photo="soya-chaap"),
        F("Classic Paneer Tikka", "369", "Cottage cheese marinated with hung curd and Indian spices, with cucumber onion salad.",
          tags=["tandoor", *STARTER, "paneer"]),
        F("Dakshini Paneer Tikka", "379", "Southern spices and cottage cheese grilled in a tandoor, with onion pachadi.",
          tags=["tandoor", *STARTER, "paneer"]),
        F("Moroccan Paneer Tikka", "379", "Moroccan-spiced cottage cheese grilled and served with olive dust and thecha dip.",
          tags=["tandoor", *STARTER, "paneer", "jain-available"]),
        F("Cream Cheese Malai Paneer Tikka", "389", "Silky paneer marinated in cream cheese and malai, grilled to melt-in-mouth.",
          tags=["tandoor", *STARTER, "paneer", "jain-available"]),
        F("Corn Kees", "399", "Sweet corn with aromatic spices, podi dust and a curry leaf tadka.",
          tags=["tandoor", *STARTER], special=True),
        F("Broccoli Boondi Phool", "399", "A crunchy medley of broccoli florets tossed in bold flavours.",
          tags=["tandoor", *STARTER, "jain-available"], special=True, photo="broccoli-boondi-phool"),
        F("Red Marinated Kumbh Tikka", "389", "Red-spiced marinated button mushrooms grilled in a tandoor.",
          tags=["tandoor", *STARTER]),
        F("Kesar Malai Soya", "389", "Malai-marinated soya grilled in the tandoor.",
          tags=["tandoor", *STARTER, "jain-available"]),
    ]),
    cat("Local Connects", "local-connects", "Rooted in heritage and bursting with regional flair.", [
        F("Ghee Roast Mushroom", "349", "South Indian-style roast in rich ghee for a flavourful bite.",
          tags=[*STARTER, "south indian"], photo="ghee-roast-mushroom"),
        F("Ghee Roast Paneer", "389", "South Indian-style paneer roasted in rich ghee.", tags=[*STARTER, "south indian", "paneer"]),
        F("Ghee Roast Broccoli", "389", "South Indian-style broccoli roasted in rich ghee.", tags=[*STARTER, "south indian"]),
        F("Andhra Chilli Mushroom", "349", "Andhra-style mushroom tossed in spicy green chilli masala with a heat kick.",
          tags=[*STARTER, "south indian"], vegan=True),
        F("Andhra Chilli Paneer", "389", "Andhra-style paneer tossed in spicy green chilli masala with a heat kick.",
          tags=[*STARTER, "south indian", "paneer", "jain-available"]),
        F("Andhra Chilli Broccoli", "389", "Andhra-style broccoli tossed in spicy green chilli masala with a heat kick.",
          tags=[*STARTER, "south indian", "jain-available"], vegan=True),
    ]),
    cat("Asian Bliss", "asian-bliss", "Tangy, spicy and savoury - an ode to Eastern flavours.", [
        F("Lotus Stem Pepper Salt", "349", "Lotus stems steamed and tossed in a pepper-salt mix - light and crunchy.",
          tags=["asian", *STARTER], vegan=True),
        F("Fried Veggie Wonton", "369", "Crispy golden wontons filled with seasoned veggies, with a tangy dipping sauce.",
          tags=["asian", *STARTER]),
        F("Schezwan Chilli Babycorn", "349", "Crunchy babycorn tossed in fiery Schezwan sauce.",
          tags=["asian", *STARTER, "jain-available"], vegan=True),
        F("Butter Garlic Mushroom", "369", "Juicy mushrooms sautéed in rich butter and aromatic garlic.",
          tags=["asian", *STARTER]),
        F("Kung Pao Baby Potato", "349", "Crispy baby potatoes glazed in a sweet, spicy Kung Pao sauce with crunchy peanuts.",
          tags=["asian", *STARTER], vegan=True, photo="kung-pao-baby-potato"),
        F("Mountain Chilli Paneer", "379", "Wok-tossed paneer in a spicy mountain-style chilli sauce.",
          tags=["asian", *STARTER, "paneer", "jain-available"]),
        F("Pan Fried Paneer Satay", "389", "Paneer skewers marinated in Asian spices, served with a savoury satay dip.",
          tags=["asian", *STARTER, "paneer"], special=True, photo="paneer-satay"),
        F("Thai Corn Crispers", "389", "Crispy golden corn fritters with Thai herbs and a sweet-spicy dipping sauce.",
          tags=["asian", *STARTER], vegan=True),
        F("Thai Golden Bag", "389", "Crispy pouches filled with spiced vegetables and herbs, bursting with Thai flavours.",
          tags=["asian", *STARTER], special=True),
    ]),
    cat("Bao & Dimsums", "bao-dimsums", "Soft buns and delicate dumplings, steamed to perfection.", [
        F("Broccoli Cashewnut Dumpling", "429", "Delicate dumplings packed with broccoli and roasted cashews.",
          tags=["dimsum", *STARTER], special=True, photo="broccoli-cashewnut-dumpling"),
        F("Cream Cheese Dumpling", "459", "Silky dumplings filled with rich cream cheese and herbs.", tags=["dimsum", *STARTER]),
        F("Crunchy Vegetable Dumpling", "439", "Dumplings filled with a medley of seasoned crunchy vegetables.",
          tags=["dimsum", *STARTER]),
        F("Corn & Spinach Dumpling", "439", "Soft dumplings stuffed with sweet corn and spinach.", tags=["dimsum", *STARTER]),
        F("Kung Pao Veg Bao", "459", "Steamed bao loaded with spicy Kung Pao vegetables and crunchy peanuts.",
          tags=["bao", *STARTER]),
        F("Panko Cottage Cheese Bao", "479", "Fluffy bao stuffed with crispy panko-crusted paneer and zesty sauces.",
          tags=["bao", *STARTER, "paneer"]),
        F("Tiger Bao with Yellow Curry", "499", "Crusted bao with spicy vegetable and mushroom, alongside yellow curry.",
          tags=["bao", *STARTER], special=True),
    ]),
    cat("Asian Bowls & Curries", "asian-bowls", "Travel the world, one bowl at a time.", [
        F("Vegetable & Tofu Ramen Noodle Bowl", "569", "Carrot, asparagus, broccoli, beetroot pickle and tofu in a chilli garlic broth.",
          tags=["bowl", "ramen", *MAIN], special=True, vegan=True),
        F("Khow Suey", "569", "Burmese coconut noodle broth bowl loaded with assorted condiments.",
          tags=["bowl", *MAIN], special=True, vegan=True),
        F("Mongolian Hot Bowl", "559", "Sizzling stir-fried veggies and noodles in a bold, smoky Mongolian sauce.",
          tags=["bowl", *MAIN], vegan=True, photo="mongolian-hot-bowl"),
        F("Garlic & Chilli Ramen Bowl", "549", "Fragrant ramen simmered in a spicy garlic-chilli broth, packed with umami.",
          tags=["bowl", "ramen", *MAIN], vegan=True),
        F("Thai Red Curry", "399", "Bold and creamy curry with red Thai spices and veggies.", tags=["curry", *MAIN], vegan=True),
        F("Thai Green Curry", "399", "Creamy coconut curry with green Thai spices and veggies.", tags=["curry", *MAIN], vegan=True),
        F("Mexican Cottage Cheese Bowl with Cilantro Rice", "439", "Grilled cottage cheese over zesty cilantro rice, Mexican-style.",
          tags=["bowl", *MAIN, "paneer"]),
    ]),
    cat("Pastas & Risotto", "pastas", "Continental classics with flair.", [
        F("Classic Creamy Cheese Sauce Pasta", "389", "Silky pasta tossed in a rich, velvety cheese sauce.",
          tags=["pasta", *MAIN, "jain-available"]),
        F("Aglio Olio Peperoncino", "389", "Classic AOP pasta from southern Italy.", tags=["pasta", *MAIN], photo="aglio-olio"),
        F("Mac & Cheese Pasta with Garlic Bread", "399", "Creamy macaroni served with crispy garlic bread.",
          tags=["pasta", *MAIN, "jain-available"]),
        F("Ratatouille Lasagna", "449", "Lasagna layered with roasted veggies and topped with a luscious cream cheese sauce.",
          tags=["pasta", "lasagna", *MAIN], special=True),
        F("Spinach & Monterey Jack Cannelloni", "429", "Cannelloni stuffed with spinach and Monterey Jack cheese.",
          tags=["pasta", *MAIN]),
        F("Creamy Mushroom Risotto", "449", "Arborio rice with fresh herbs, cooked in a creamy mushroom sauce.",
          tags=["risotto", *MAIN], special=True),
    ]),
    cat("Indian Delights", "indian-delights", "Served with assortments and pickle. The soul of India - bold, aromatic and diverse.", [
        F("Old Fashioned Malai Kofta", "349", "Soft koftas in a creamy, mild gravy.", tags=["curry", *MAIN, "jain-available"]),
        F("Ghee Dal Tadka", "249", "Comforting yellow dal tempered with ghee.", tags=["dal", *MAIN]),
        F("Kadhi Chawal", "309", "Tangy yogurt curry with steamed rice, pickle and papad.", tags=["curry", *MAIN, "jain-available"]),
        F("Maa ki Dal", "289", "Slow-cooked mixed dal in a creamy tomato gravy, with butter roti.", tags=["dal", *MAIN, "jain-available"]),
        F("Multani Chole", "329", "Smoky chickpea curry from Muradabad, with Muradabadi kulcha.", tags=["curry", *MAIN]),
        F("Slow Cooked Dal Makhani", "319", "Black lentils slow-cooked with cream and spices.", tags=["dal", *MAIN]),
        F("Paneer & Spinach Lasagna", "349", "Paneer and spinach baked in a luscious tomato cream sauce, with mirchi parantha.",
          tags=[*MAIN, "paneer"], special=True),
        F("Spinach and Cheese Roulade", "379", "Rolled spinach and cheese baked to golden perfection, with butter dhaniya paratha.",
          tags=[*MAIN], special=True),
        F("Kashmiri Aloo Dum", "329", "Stuffed potato curry from Kashmir, slow-cooked in a curd-based gravy.", tags=["curry", *MAIN]),
        F("Taka Tak Paneer", "369", "Spicy, street-style paneer tossed on the tawa with bold Punjabi flavours.",
          tags=["curry", *MAIN, "paneer", "jain-available"]),
        F("Dingri Matar Masala", "369", "Mushrooms and peas in a spiced onion-tomato gravy.", tags=["curry", *MAIN], vegan=True),
        F("Achaari Bhindi", "329", "Okra stir-fried with tangy pickling spices.", tags=["sabzi", *MAIN], vegan=True),
        F("Aloo Paneer Matar", "369", "Potatoes, paneer and peas in a homestyle curry.", tags=["curry", *MAIN, "paneer"]),
        F("Aloo Matar", "369", "Potatoes and peas in a homestyle curry (from the vegan menu).", tags=["curry", *MAIN], vegan=True),
        F("Kadhai Paneer", "389", "Paneer tossed with bell peppers and onions in a bold, rustic kadhai masala.",
          tags=["curry", *MAIN, "paneer"]),
        F("Paneer Pasanda", "389", "Stuffed paneer in a rich, nutty gravy, with kasuri methi parantha.",
          tags=["curry", *MAIN, "paneer", "jain-available"]),
        F("Paneer Makhani", "389", "Creamy tomato-butter paneer curry.", tags=["curry", *MAIN, "paneer", "jain-available"]),
        F("Rajasthani Saag Subzi", "369", "A traditional Rajasthani green leafy sabzi, full of earthy flavours.",
          tags=["sabzi", *MAIN], vegan=True),
        F("Kaju Masala", "389", "Royal curry of whole cashews simmered in a tomato gravy.", tags=["curry", *MAIN]),
        F("Lasooni Saag Burrata", "409", "Garlicky saag paired with creamy burrata - desi meets gourmet.",
          tags=["curry", *MAIN], special=True, photo="lasooni-saag-burrata"),
        F("Paneer Afghani", "389", "Mildly spiced, creamy paneer curry rich with cashew.",
          tags=["curry", *MAIN, "paneer", "jain-available"]),
    ]),
    cat("Rice & Biryani", "rice", "Soul-warming rice, pulao and khichdi.", [
        F("Chandramukhi Biryani", "409", "Kolkata-style veg biryani with our own Chandramukhi twist, with mirchi raita.",
          tags=["biryani", "rice", *MAIN], photo="chandramukhi-biryani"),
        F("Shahi Veg Pulao", "339", "Aromatic basmati rice cooked with mixed veg and dry fruits.", tags=["rice", *MAIN, "jain-available"]),
        F("Namma Curd Rice", "219", "Mashed rice with curd and a South Indian tadka, with cashew crumble.",
          tags=["rice", *MAIN, "south indian", "jain-available"]),
        F("Mix Veg Dal Khichdi", "259", "One-pot lentils and rice.", tags=["rice", "khichdi", *MAIN, "jain-available"]),
        F("Steamed Rice", "179", "Long-grain plain steamed rice.", tags=["rice", "side"]),
        F("Kaju Ghee Rice", "219", "Simple, indulgent rice with ghee and cashew nuts.", tags=["rice", "side", "jain-available"]),
        F("Jeera Corn Methi Pulao", "219", "Rice tossed with cumin, corn and fenugreek leaves.", tags=["rice", *MAIN], vegan=True),
        F("Ghee Palak Khichdi", "279", "Rice, lentils and spinach cooked together in ghee.", tags=["rice", "khichdi", *MAIN, "jain-available"]),
    ]),
    cat("Fried Rice & Noodles", "noodles", "Wok-tossed rice and slurpy noodles.", [
        F("Black Bean Fried Rice", "339", "Wok-tossed rice with savoury black bean sauce and crunchy vegetables.", tags=["rice", "asian", *MAIN]),
        F("Burnt Garlic Fried Rice / Noodles", "309", "Fragrant rice or noodles tossed with golden burnt garlic and veggies.",
          tags=["rice", "noodles", "asian", *MAIN], sizes=[("Fried Rice", "309"), ("Noodles", "349")]),
        F("Thai Basil Fried Rice / Noodles", "319", "Spicy Thai-style fried rice or noodles with fresh basil and chilli.",
          tags=["rice", "noodles", "asian", *MAIN], sizes=[("Fried Rice", "319"), ("Noodles", "349")], vegan=True),
        F("Chilli Garlic Noodles", "349", "Noodles tossed with bold garlic and red chilli.", tags=["noodles", "asian", *MAIN]),
        F("Roasted Garlic Noodles", "349", "Noodles infused with rich roasted garlic.", tags=["noodles", "asian", *MAIN]),
        F("Spicy Chilli Coriander Noodles", "349", "Fiery noodles tossed with fresh coriander and red chillies.",
          tags=["noodles", "asian", *MAIN], vegan=True, photo="chilli-coriander-noodles"),
        F("Pad Thai Noodles", "349", "Pad Thai noodles in a sweet, tangy sauce with peanuts and veggies.", tags=["noodles", "asian", *MAIN]),
        F("Hakka Noodles", "349", "Classic Indo-Chinese noodles stir-fried with veggies and soy sauce.",
          tags=["noodles", "asian", *MAIN], vegan=True),
        F("Hibachi Fried Rice", "369", "Japanese-style stir-fried rice with soy sauce and grilled veggies.",
          tags=["rice", "asian", *MAIN], vegan=True),
        F("Blue Pea Rice", "369", "Vibrant blue rice infused with butterfly pea flower and subtle herbs.", tags=["rice", "asian", *MAIN]),
    ]),
    cat("Indian Breads", "breads", "Served with papad and pickle. Warm, golden and made for gravies.", [
        F("Garlic Roti", "109", "Garlic-topped crispy roti.", tags=["bread", "roti", "side"]),
        F("Tandoori Roti", "79", "Whole wheat flatbread cooked in a clay oven.", tags=["bread", "roti", "side"]),
        F("Missi Roti", "89", "Spiced gram flour roti with a dollop of white butter.", tags=["bread", "roti", "side"]),
        F("Multigrain Roti", "99", "Wholesome roti made with a mix of grains.", tags=["bread", "roti", "side", "healthy"]),
        F("Jalapeño Cheddar Cheese Naan", "129", "Spicy and cheesy naan with jalapeños and melted cheese.", tags=["bread", "naan", "side"]),
        F("Pickled Garlic Naan", "119", "Bold, aromatic naan with tangy pickled garlic.", tags=["bread", "naan", "side"]),
        F("Sesame Naan", "109", "Soft naan topped with toasted sesame seeds.", tags=["bread", "naan", "side"]),
        F("Chur Chur Naan", "169", "Flaky, crushed layered naan - crisp outside, soft inside.", tags=["bread", "naan", "side"]),
        F("Plain Naan", "109", "Soft naan cooked in the tandoor.", tags=["bread", "naan", "side"]),
        F("Kashmiri Naan", "149", "Sweet, rich naan stuffed with dry fruits.", tags=["bread", "naan", "side"]),
        F("Aloo Matar Cheese Kulcha", "189", "Sourdough kulcha stuffed with potato, peas and melty cheese.", tags=["bread", "kulcha", "side"]),
        F("Pizza Kulcha", "209", "Sourdough kulcha stuffed with cheesy pizza-style veggies and herbs.", tags=["bread", "kulcha", "side"]),
        F("Paneer Cheese Kulcha", "189", "Sourdough kulcha filled with spiced paneer and melted cheese.", tags=["bread", "kulcha", "side"]),
        F("Muradabadi Kulcha", "189", "Lentil kulcha with Muradabadi spices.", tags=["bread", "kulcha", "side"]),
        F("Butter Dhaniya Kulcha", "189", "Clay pot kulcha topped with coriander and butter.",
          tags=["bread", "kulcha", "side"], photo="butter-dhaniya-kulcha"),
        F("Delhi Wale Bharwan Kulcha", "229", "Classic Delhi-style stuffed kulcha with bold, tangy flavours.", tags=["bread", "kulcha", "side"]),
    ]),
    cat("Sides", "sides", "Papads, pickles and cooling curds to round out the meal.", [
        F("Collection of Achar", "109", "A vibrant assortment of regional Indian pickles.", tags=["side"]),
        F("Papad Basket", "199", "Crisp assorted papads with tangy chutneys.", tags=["side", "shareable"], photo="papad-basket"),
        F("Bowl of Ghee", "109", "Pure golden ghee, served warm.", tags=["side"]),
        F("Plain Curd", "69", "Smooth, chilled homemade curd.", tags=["side"]),
        F("Raita", "89", "Refreshing yogurt raita with your choice of topping.", tags=["side"],
          sizes=[("Classic", "89"), ("Boondi", "89"), ("Pineapple", "89")]),
        F("Aloo Salli", "79", "Crispy potato straws.", tags=["side"]),
        F("Home Made Pickled Vegetables", "89", "Seasonal vegetables pickled the traditional way.", tags=["side"]),
    ]),
    cat("Desserts", "desserts", "From creamy classics to indulgent chocolate - the sweetest finale.", [
        F("Textures of Chocolate", "449", "A decadent trio of jaggery, mousse and velvety chocolate ganache.",
          kind="dessert", tags=["dessert", "chocolate", "jain-available"], special=True, photo="textures-of-chocolate", sweet=5),
        F("Malai Cheeni Toast", "309", "Toast layered with creamy malai and a sprinkle of sugar.",
          kind="dessert", tags=["dessert", "jain-available"], sweet=4),
        F("Water Chestnut Rubic", "329", "Delicate water chestnut cubes in rose-kissed coconut milk - light and fragrant.",
          kind="dessert", tags=["dessert"], vegan=True, sweet=3),
        F("Pheni Sheer Khurma", "349", "Rich vermicelli dessert with candied nuts and creamy saffron milk.",
          kind="dessert", tags=["dessert", "jain-available"], sweet=4),
        F("Kalakand Saw Dust", "419", "Soft kalakand, airy mousse and berry compote with a hint of crunch.",
          kind="dessert", tags=["dessert", "jain-available"], sweet=4),
    ]),
    cat("Jain Menu", "jain-menu", "Prepared Jain-style (no onion, garlic or root vegetables). Dishes marked Jain-available elsewhere can also be made Jain - ask staff.", [
        F("Paneer Cheese Khakhra Tostado (Jain)", "369", "A crispy khakhra base topped with cheesy paneer goodness.",
          tags=["jain", "appetizer", *STARTER]),
        F("Red Marinated Paneer Tikka (Jain)", "369", "Red-spiced marinated paneer grilled in a tandoor.",
          tags=["jain", "tandoor", *STARTER, "paneer"]),
        F("Veg Fried Rice (Jain)", "309", "Wok-tossed rice with fresh vegetables and aromatic seasoning.", tags=["jain", "rice", *MAIN]),
        F("Hakka Noodles (Jain)", "329", "Classic Indo-Chinese noodles stir-fried with veggies and soy sauce.", tags=["jain", "noodles", *MAIN]),
        F("Mix Vegetable Makhani (Jain)", "309", "Creamy tomato gravy with assorted vegetables.", tags=["jain", "curry", *MAIN]),
        F("Matar Paneer (Jain)", "369", "Paneer and peas in a homestyle curry.", tags=["jain", "curry", *MAIN, "paneer"]),
        F("Multani Chole with Muradabadi Kulcha (Jain)", "349", "Smoky chickpea curry with Muradabadi kulcha.",
          tags=["jain", "curry", *MAIN]),
    ]),
]
