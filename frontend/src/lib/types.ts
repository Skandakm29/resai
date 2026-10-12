// Mirrors the FastAPI response schemas (backend/app/schemas).
export type TriState = "yes" | "no" | "unknown";

export interface Variant {
  id: string;
  name: string;
  price: string;
  is_default: boolean;
  is_available: boolean;
}

export interface Addon {
  id: string;
  name: string;
  group_name: string;
  price: string;
  is_available: boolean;
}

export interface KnownList {
  status: "verified" | "partial" | "unknown";
  items: string[];
}

export interface MenuItem {
  id: string;
  category_id: string;
  category_name: string;
  name: string;
  description: string | null;
  price: string;
  price_from: string;
  currency: string;
  is_available: boolean;
  image_url: string | null;
  item_type: "beverage" | "food" | "dessert";
  temperature: "hot" | "cold" | null;
  contains_coffee: boolean | null;
  caffeine_level: string | null;
  strength: number | null;
  sweetness: number | null;
  serves: number;
  dietary: { vegetarian: TriState; vegan: TriState };
  dietary_labels: string[];
  ingredients: KnownList;
  allergens: KnownList;
  flavor_tags: string[];
  variant_required: boolean;
  variants: Variant[];
  addons: Addon[];
  is_featured: boolean;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  item_count: number;
  items: MenuItem[];
}

export interface Menu {
  restaurant_slug: string;
  currency: string;
  categories: Category[];
}

export interface Restaurant {
  id: string;
  slug: string;
  name: string;
  tagline: string | null;
  address_line: string | null;
  city: string | null;
  phone: string | null;
  logo_url: string | null;
  currency: string;
  settings: {
    assistant_name: string;
    welcome_message: string;
    suggested_prompts: string[];
    ai_enabled: boolean;
    pickup_enabled: boolean;
    ordering_enabled: boolean;
    allergen_disclaimer: string;
    brand_color: string | null;
    assistant_icon: string;
  };
}

export interface Recommendation {
  item: MenuItem;
  reasons: string[];
  note: string | null;
  suggested_quantity: number;
  estimated_total: string;
  over_budget: boolean;
}

export interface Comparison {
  item_ids: string[];
  item_names: string[];
  rows: { label: string; values: string[] }[];
}

export type Course = "starter" | "main" | "dessert" | "drink";

export interface PlanLine {
  course: Course;
  item: MenuItem;
  variant_id: string | null;
  variant_name: string | null;
  quantity: number;
  unit_price: string;
  line_total: string;
}

export interface MealPlan {
  party_size: number;
  budget: string | null;
  lines: PlanLine[];
  course_subtotals: { course: Course; items: number; subtotal: string }[];
  total: string;
  per_person: string;
  remaining: string | null;
  within_budget: boolean;
  assumptions: string[];
}

export interface ChatResponse {
  conversation_id: string;
  message: string;
  intent: string;
  recommendations: Recommendation[];
  comparison: Comparison | null;
  plan?: MealPlan | null;
  clarification: { question: string; options: string[] } | null;
  follow_ups: string[];
  filter_summary: string[];
  source: "llm" | "rules";
}

export interface CartValidationLine {
  item_id: string;
  name: string | null;
  variant_id: string | null;
  variant_name: string | null;
  addons: { id: string; name: string; price: string }[];
  quantity: number;
  unit_price: string | null;
  line_total: string;
  status: "ok" | "price_changed" | "unavailable" | "invalid";
  issues: string[];
}

export interface CartValidation {
  valid: boolean;
  currency: string;
  lines: CartValidationLine[];
  subtotal: string;
  item_count: number;
  ordering_enabled: boolean;
  message: string;
}
