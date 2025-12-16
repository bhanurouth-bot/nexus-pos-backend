from rest_framework import serializers
from .models import Ingredient, Recipe, Restaurant, Category, MenuItem, Order, OrderItem, Table
from .models import VariantGroup, VariantOption, Ingredient, Recipe # <--- Added Imports

# --- NEW: INVENTORY SERIALIZERS ---
class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'current_stock', 'unit']

class RecipeSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    ingredient_unit = serializers.CharField(source='ingredient.unit', read_only=True)
    
    class Meta:
        model = Recipe
        fields = ['id', 'ingredient', 'ingredient_name', 'ingredient_unit', 'quantity_required']

class VariantOptionSerializer(serializers.ModelSerializer):
    recipes = RecipeSerializer(many=True, read_only=True) # <--- Show recipes for this variant

    class Meta:
        model = VariantOption
        fields = ['id', 'name', 'price_adjustment', 'recipes']

class VariantGroupSerializer(serializers.ModelSerializer):
    options = VariantOptionSerializer(many=True, read_only=True)

    class Meta:
        model = VariantGroup
        fields = ['id', 'name', 'is_required', 'allow_multiple', 'options']

class MenuItemSerializer(serializers.ModelSerializer):
    variant_groups = VariantGroupSerializer(many=True, read_only=True)
    recipes = RecipeSerializer(many=True, read_only=True) # <--- Show base recipes

    class Meta:
        model = MenuItem
        fields = ['id', 'category', 'name', 'description', 'price', 'is_available', 'image', 'variant_groups', 'recipes']

class CategorySerializer(serializers.ModelSerializer):
    menu_items = MenuItemSerializer(many=True, read_only=True, source='menuitem_set')

    class Meta:
        model = Category
        fields = ['id', 'name', 'menu_items']

class RestaurantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = ['id', 'name', 'address']

class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ['id', 'name', 'is_occupied']

# --- UPDATED: Includes selected options in the receipt/response ---
class OrderItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source='menu_item.name', read_only=True)
    selected_options = VariantOptionSerializer(many=True, read_only=True)

    class Meta:
        model = OrderItem
        fields = ['menu_item', 'menu_item_name', 'quantity', 'price_at_time_of_order', 'selected_options']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True) 

    class Meta:
        model = Order
        fields = ['id', 'restaurant', 'table', 'status', 'total_amount', 'items', 'customer_name', 'customer_phone']

class KitchenItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source='menu_item.name')
    variants = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['quantity', 'menu_item_name', 'variants']

    def get_variants(self, obj):
        return ", ".join([opt.name for opt in obj.selected_options.all()])

class KitchenOrderSerializer(serializers.ModelSerializer):
    table_name = serializers.CharField(source='table.name')
    waiter_name = serializers.CharField(source='waiter.name', default="Unknown")
    items = KitchenItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'table_name', 'waiter_name', 'created_at', 'items']