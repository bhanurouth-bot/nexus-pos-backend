from django.contrib import admin
from .models import Restaurant, Category, MenuItem, Table, Order, OrderItem, VariantGroup, VariantOption, Waiter, Ingredient, Recipe

# 1. Inline for Recipes (Works for both MenuItems and Variants)
class RecipeInline(admin.TabularInline):
    model = Recipe
    extra = 1
    fk_name = "menu_item" # Default for Menu Item page

# 2. Inline for Variants inside Menu Item
class VariantOptionInline(admin.TabularInline):
    model = VariantOption
    extra = 1

class VariantGroupInline(admin.StackedInline):
    model = VariantGroup
    inlines = [VariantOptionInline] # Note: Nested inlines don't work natively in Django basic admin, 
                                    # so we usually edit Options separately or use a specialized package.
                                    # For simplicity, we will register VariantOption separately below.
    extra = 0

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price']
    inlines = [VariantGroupInline, RecipeInline] 

@admin.register(VariantGroup)
class VariantGroupAdmin(admin.ModelAdmin):
    inlines = [VariantOptionInline]

# --- NEW: Allow adding Recipes to specific Variants (e.g., Large, Extra Cheese) ---
@admin.register(VariantOption)
class VariantOptionAdmin(admin.ModelAdmin):
    list_display = ['name', 'group', 'price_adjustment']
    # We use a special inline that points to the 'variant_option' field
    class VariantRecipeInline(admin.TabularInline):
        model = Recipe
        extra = 1
        fk_name = "variant_option"
    
    inlines = [VariantRecipeInline]

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ['name', 'current_stock', 'unit']

admin.site.register(Restaurant)
admin.site.register(Category)
admin.site.register(Table)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Waiter)