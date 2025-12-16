from django.db import models
import uuid
from decimal import Decimal

# 1. The Restaurant
class Restaurant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# 2. Categories
class Category(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class Waiter(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    pin_code = models.CharField(max_length=4)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

# 3. Menu Items
class MenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='menu_images/', blank=True, null=True)

    def __str__(self):
        return self.name
    
    # --- NEW: CALCULATE FOOD COST ---
    def get_approx_cost(self):
        cost = Decimal('0.00')
        # Sum up cost of all ingredients in the base recipe
        for recipe in self.recipes.all():
            cost += (recipe.quantity_required * recipe.ingredient.cost_per_unit)
        return cost

    def get_profit_margin(self):
        cost = self.get_approx_cost()
        if self.price == 0: return 0
        return round(((self.price - cost) / self.price) * 100, 2)

class VariantGroup(models.Model):
    menu_item = models.ForeignKey(MenuItem, related_name='variant_groups', on_delete=models.CASCADE)
    name = models.CharField(max_length=50) 
    is_required = models.BooleanField(default=True) 
    allow_multiple = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.menu_item.name} - {self.name}"

class VariantOption(models.Model):
    group = models.ForeignKey(VariantGroup, related_name='options', on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    price_adjustment = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.name} (+{self.price_adjustment})"

# 4. Tables
class Table(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    is_occupied = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.restaurant.name} - {self.name}"

# --- NEW: RESERVATIONS MODEL ---
class Reservation(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, blank=True)
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=15)
    reservation_time = models.DateTimeField()
    guests = models.IntegerField(default=2)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.customer_name} ({self.reservation_time})"

# 5. Orders
class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('READY', 'Ready'),
        ('PAID', 'Paid'),
        ('COMPLETED', 'Completed'),
    ]
    id = models.AutoField(primary_key=True) 
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True)
    waiter = models.ForeignKey(Waiter, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    customer_phone = models.CharField(max_length=15, blank=True, null=True)
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # --- NEW: KITCHEN PERFORMANCE METRICS ---
    created_at = models.DateTimeField(auto_now_add=True) # When Waiter Placed it
    ready_at = models.DateTimeField(null=True, blank=True) # When Kitchen Marked Ready
    completed_at = models.DateTimeField(null=True, blank=True) # When Cashier Closed it

    @property
    def preparation_time_minutes(self):
        if self.ready_at and self.created_at:
            diff = self.ready_at - self.created_at
            return round(diff.total_seconds() / 60, 1)
        return None

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    selected_options = models.ManyToManyField(VariantOption, blank=True)
    price_at_time_of_order = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.name}"

# ==========================================
# 6. INVENTORY SYSTEM
# ==========================================

class Ingredient(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    current_stock = models.DecimalField(max_digits=10, decimal_places=3, default=0.000) 
    unit = models.CharField(max_length=20)
    
    # --- NEW: PROFIT TRACKING ---
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) 
    
    def __str__(self):
        return f"{self.name} ({self.current_stock} {self.unit})"

class Recipe(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='recipes', null=True, blank=True)
    variant_option = models.ForeignKey(VariantOption, on_delete=models.CASCADE, related_name='recipes', null=True, blank=True)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity_required = models.DecimalField(max_digits=10, decimal_places=3) 

    def __str__(self):
        return f"Recipe Step"