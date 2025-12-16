from datetime import timedelta, timezone
from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
from django.utils import timezone
import datetime
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Reservation, Restaurant, Category, MenuItem, Table, Order, OrderItem, Waiter
from .models import VariantGroup, VariantOption, Ingredient, Recipe
from .serializers import IngredientSerializer, RestaurantSerializer, CategorySerializer, KitchenOrderSerializer, TableSerializer, OrderSerializer

# =========================================
#  APP APIs (Android)
# =========================================

@api_view(['POST'])
@csrf_exempt
@authentication_classes([]) 
@permission_classes([])
@transaction.atomic
def create_order(request):
    data = request.data
    try:
        restaurant_id = data.get('restaurant_id')
        table_id = data.get('table_id')
        waiter_id = data.get('waiter_id')
        items_data = data.get('items')
        
        # NEW: Extract Customer Details
        c_name = data.get('customer_name', 'Guest')
        c_phone = data.get('customer_phone', '')

        restaurant = get_object_or_404(Restaurant, id=restaurant_id)
        table = get_object_or_404(Table, id=table_id)
        waiter = Waiter.objects.filter(id=waiter_id).first() if waiter_id else None

        order = Order.objects.create(
            restaurant=restaurant,
            table=table,
            waiter=waiter,
            status='PENDING',
            customer_name=c_name,   # Save Name
            customer_phone=c_phone  # Save Phone
        )

        total_bill = Decimal('0.00')

        for item in items_data:
            menu_item = get_object_or_404(MenuItem, id=item['id'])
            qty = Decimal(item['qty'])
            input_option_ids = set(item.get('selected_options', []))
            
            # --- INVENTORY LOGIC ---
            recipes_to_process = []
            recipes_to_process.extend(menu_item.recipes.all()) # Base Recipes
            
            if input_option_ids:
                selected_variants = VariantOption.objects.filter(id__in=input_option_ids).prefetch_related('recipes')
                for variant in selected_variants:
                    recipes_to_process.extend(variant.recipes.all()) # Variant Recipes

            for recipe in recipes_to_process:
                ingredient = recipe.ingredient
                required_amount = recipe.quantity_required * qty
                
                if ingredient.current_stock < required_amount:
                    raise Exception(f"Out of Stock: {ingredient.name}. Need {required_amount}, have {ingredient.current_stock}")
                
                ingredient.current_stock -= required_amount
                ingredient.save()
            # -----------------------

            # Validate Groups
            valid_groups = menu_item.variant_groups.prefetch_related('options').all()
            for group in valid_groups:
                group_option_ids = {opt.id for opt in group.options.all()}
                selected_in_group = input_option_ids.intersection(group_option_ids)
                if group.is_required and not selected_in_group:
                    raise Exception(f"Selection required for '{group.name}'")
                if not group.allow_multiple and len(selected_in_group) > 1:
                    raise Exception(f"Only one selection allowed for '{group.name}'")

            # Calculate Price
            price = menu_item.price
            options_to_add = []
            if input_option_ids:
                options_to_add = VariantOption.objects.filter(id__in=input_option_ids)
                for opt in options_to_add:
                    price += opt.price_adjustment

            order_item = OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                quantity=item['qty'],
                price_at_time_of_order=price
            )
            
            if options_to_add:
                order_item.selected_options.set(options_to_add)

            total_bill += (price * qty)

        order.total_amount = total_bill
        order.save()
        
        table.is_occupied = True
        table.save()

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "kitchen_group",
            {
                "type": "order_notification",
                "order": {
                    "id": order.id,
                    "table": order.table.name,
                    "items": [
                        f"{item.quantity} x {item.menu_item.name}"
                        for item in order.items.all()
                    ],
                    "total": str(order.total_amount)
                }
            }
        )

        return Response({"message": "success", "order_id": order.id}, status=status.HTTP_201_CREATED)

    except Exception as e:
        # ADD THIS LINE TO SEE THE ERROR IN YOUR TERMINAL
        print(f"❌ ORDER ERROR: {str(e)}") 
        import traceback
        traceback.print_exc() # Prints the line number of the error
        
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    

@api_view(['GET'])
@authentication_classes([])
@permission_classes([]) 
def get_restaurant_menu(request, restaurant_id):
    try:
        restaurant = Restaurant.objects.get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        return Response({"error": "Restaurant not found"}, status=404)
    categories = Category.objects.filter(restaurant=restaurant)
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@authentication_classes([])
@permission_classes([]) 
def get_tables(request, restaurant_id):
    tables = Table.objects.filter(restaurant__id=restaurant_id)
    serializer = TableSerializer(tables, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@csrf_exempt
@authentication_classes([])
@permission_classes([]) 
def waiter_login(request):
    pin = request.data.get('pin')
    restaurant_id = request.data.get('restaurant_id')
    waiter = Waiter.objects.filter(restaurant__id=restaurant_id, pin_code=pin, is_active=True).first()
    
    if waiter:
        return Response({
            "status": "success", 
            "waiter_id": waiter.id, 
            "waiter_name": waiter.name
        })
    return Response({"error": "Invalid PIN"}, status=400)

@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def get_active_orders(request, restaurant_id):
    # Fetch orders that are NOT completed/paid yet
    orders = Order.objects.filter(
        restaurant__id=restaurant_id, 
        status__in=['PENDING', 'READY']
    ).order_by('-created_at')
    
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data)


# =========================================
#  KITCHEN APIs (Browser)
# =========================================

@api_view(['GET'])
@authentication_classes([])
@permission_classes([]) # Fixes 403 on polling
def get_kitchen_orders(request):
    orders = Order.objects.filter(status='PENDING').order_by('created_at')
    serializer = KitchenOrderSerializer(orders, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@csrf_exempt
@authentication_classes([])
@permission_classes([])
def complete_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order.status = 'READY'
    order.ready_at = timezone.now() # <--- NEW: Track when kitchen finished
    order.save()
    return Response({"status": "success", "prep_time": order.preparation_time_minutes})

def kitchen_dashboard(request):
    return render(request, 'kitchen.html')


# =========================================
#  CASHIER APIs (Browser)
# =========================================

@api_view(['GET'])
@authentication_classes([])
@permission_classes([]) 
def get_table_bill(request, table_id):
    # Fetch ALL active orders for this table (not just the last one)
    orders = Order.objects.filter(table__id=table_id, status__in=['PENDING', 'READY'])
    
    if not orders.exists():
        return Response({"error": "No active orders"}, status=404)

    total_subtotal = Decimal('0.00')
    all_items = []

    # Aggregate Data
    for order in orders:
        total_subtotal += order.total_amount
        serializer = OrderSerializer(order)
        # Add items to the master list
        all_items.extend(serializer.data['items'])

    tax = total_subtotal * Decimal('0.05') 
    grand_total = total_subtotal + tax
    
    return Response({
        "table_id": table_id,
        "subtotal": total_subtotal,
        "tax": tax,
        "grand_total": grand_total,
        "items": all_items
    })

@api_view(['POST'])
@csrf_exempt
@authentication_classes([])
@permission_classes([]) 
def settle_table(request, table_id):
    try:
        # Get ALL active orders
        orders = Order.objects.filter(table__id=table_id, status__in=['PENDING', 'READY'])
        if not orders.exists():
            return Response({"error": "No active orders to settle"}, status=400)
            
        table = Table.objects.get(id=table_id)
        
        with transaction.atomic():
            # Mark all as COMPLETED
            orders.update(status='COMPLETED',
                          completed_at=timezone.now()
                          )
            
            # Free up the table
            table.is_occupied = False
            table.save()
            
        return Response({"status": "Table Settled"})
    except Exception as e:
        return Response({"error": str(e)}, status=400)

def cashier_dashboard(request):
    return render(request, 'cashier.html')

# =========================================
#  INVENTORY DASHBOARD APIs
# =========================================

def inventory_dashboard(request):
    return render(request, 'inventory.html')

@api_view(['GET'])
@permission_classes([])
def get_inventory_data(request, restaurant_id):
    # Get all ingredients
    ingredients = Ingredient.objects.filter(restaurant__id=restaurant_id)
    
    # Get Menu structure (Categories -> Items -> Variants)
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    categories = Category.objects.filter(restaurant=restaurant)
    
    return Response({
        "ingredients": IngredientSerializer(ingredients, many=True).data,
        "menu": CategorySerializer(categories, many=True).data
    })

@api_view(['POST'])
@csrf_exempt                # 1. Allows Browser POST
@authentication_classes([]) # 2. Disables User Login check
@permission_classes([])     # 3. Allows Public Access
def save_recipe_connection(request):
    data = request.data
    ingredient_id = data.get('ingredient_id')
    qty = data.get('qty')
    
    # We either get a menu_item_id OR a variant_id
    menu_item_id = data.get('menu_item_id')
    variant_id = data.get('variant_id')

    ingredient = get_object_or_404(Ingredient, id=ingredient_id)
    
    # 1. Check if update or create
    recipe = None
    if menu_item_id:
        recipe = Recipe.objects.filter(menu_item__id=menu_item_id, ingredient=ingredient).first()
        if not recipe:
            recipe = Recipe(menu_item_id=menu_item_id, ingredient=ingredient)
    elif variant_id:
        recipe = Recipe.objects.filter(variant_option__id=variant_id, ingredient=ingredient).first()
        if not recipe:
            recipe = Recipe(variant_option_id=variant_id, ingredient=ingredient)
            
    # 2. Update Quantity (or Delete if 0)
    if float(qty) <= 0:
        if recipe.id: recipe.delete()
        return Response({"status": "deleted"})
    
    recipe.quantity_required = qty
    recipe.save()
    
    return Response({"status": "saved", "id": recipe.id})

@api_view(['POST'])
@csrf_exempt
@permission_classes([])
def add_ingredient(request):
    name = request.data.get('name')
    unit = request.data.get('unit')
    stock = request.data.get('stock')
    restaurant_id = request.data.get('restaurant_id')
    
    Ingredient.objects.create(
        restaurant_id=restaurant_id,
        name=name,
        unit=unit,
        current_stock=stock
    )
    return Response({"status": "created"})

def analytics_dashboard(request):
    return render(request, 'analytics.html')

@api_view(['GET'])
@permission_classes([])
def get_analytics_data(request, restaurant_id):
    today = timezone.now().date()
    
    # 1. Total Sales Today
    orders_today = Order.objects.filter(
        restaurant__id=restaurant_id, 
        created_at__date=today, 
        status__in=['PAID', 'COMPLETED']
    )
    total_sales = orders_today.aggregate(Sum('total_amount'))['total_amount__sum'] or 0

    # 2. Top Selling Items (Basic Count)
    # (For a real giant-killer, we'd use complex aggregations here, but let's start simple)
    
    # 3. Low Stock Alert (Ingredients < 2.0 units)
    low_stock = Ingredient.objects.filter(
        restaurant__id=restaurant_id, 
        current_stock__lt=2.0
    ).values('name', 'current_stock', 'unit')

    return Response({
        "sales_today": total_sales,
        "order_count": orders_today.count(),
        "low_stock": list(low_stock)
    })


@api_view(['POST'])
@permission_classes([])
def make_reservation(request):
    data = request.data
    try:
        restaurant = Restaurant.objects.get(id=data.get('restaurant_id'))
        # Parse "2023-12-25 19:30:00" string to datetime
        res_time = datetime.datetime.strptime(data.get('time'), "%Y-%m-%d %H:%M:%S")
        
        Reservation.objects.create(
            restaurant=restaurant,
            customer_name=data.get('name'),
            customer_phone=data.get('phone'),
            reservation_time=res_time,
            guests=data.get('guests', 2)
        )
        return Response({"status": "Reservation Booked!"})
    except Exception as e:
        return Response({"error": str(e)}, status=400)
    
@api_view(['GET'])
@permission_classes([])
def get_analytics_data(request, restaurant_id):
    today = timezone.now().date()
    
    # 1. Financials
    orders_today = Order.objects.filter(
        restaurant__id=restaurant_id, 
        created_at__date=today, 
        status__in=['PAID', 'COMPLETED']
    )
    total_revenue = orders_today.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    # 2. Kitchen Efficiency (Avg Prep Time)
    # Filter orders that have a 'ready_at' time
    completed_orders = Order.objects.filter(restaurant__id=restaurant_id, ready_at__isnull=False)
    avg_prep_time = 0
    if completed_orders.exists():
        total_minutes = sum([o.preparation_time_minutes for o in completed_orders if o.preparation_time_minutes])
        avg_prep_time = round(total_minutes / completed_orders.count(), 1)

    # 3. Profit Analysis (Top 5 Items)
    # This loop calculates the profit for every item on the menu
    menu_performance = []
    menu_items = MenuItem.objects.filter(restaurant__id=restaurant_id)
    
    for item in menu_items:
        cost = item.get_approx_cost()
        margin = item.get_profit_margin()
        menu_performance.append({
            "name": item.name,
            "price": item.price,
            "cost": cost,
            "profit_margin": f"{margin}%"
        })
    
    # Sort by highest profit margin
    menu_performance = sorted(menu_performance, key=lambda x: float(x['profit_margin'].strip('%')), reverse=True)[:5]

    return Response({
        "revenue_today": total_revenue,
        "orders_count": orders_today.count(),
        "avg_kitchen_time": f"{avg_prep_time} mins",
        "top_profitable_items": menu_performance
    })

@api_view(['POST'])
@csrf_exempt
@permission_classes([])
def update_ingredient_cost(request):
    """
    Allows the manager to update stock and COST price.
    Essential for Profit Margin calculation.
    """
    try:
        ingredient_id = request.data.get('id')
        new_cost = request.data.get('cost_per_unit') # e.g., 50.00 (per kg)
        added_stock = request.data.get('added_stock', 0) # e.g., 10 (kg)
        
        ingredient = Ingredient.objects.get(id=ingredient_id)
        
        if new_cost is not None:
            ingredient.cost_per_unit = new_cost
            
        if added_stock:
            ingredient.current_stock += Decimal(str(added_stock))
            
        ingredient.save()
        
        return Response({"status": "updated", "new_stock": ingredient.current_stock, "cost": ingredient.cost_per_unit})
    except Exception as e:
        return Response({"error": str(e)}, status=400)

@api_view(['POST'])
@permission_classes([])
def make_reservation(request):
    data = request.data
    try:
        restaurant_id = data.get('restaurant_id')
        table_id = data.get('table_id') # Optional: User might just want "Any table"
        res_time_str = data.get('time') # Format: "2023-12-25 19:30:00"
        guests = int(data.get('guests', 2))
        
        restaurant = Restaurant.objects.get(id=restaurant_id)
        res_time = datetime.datetime.strptime(res_time_str, "%Y-%m-%d %H:%M:%S")
        
        # LOGIC: A standard reservation lasts 2 hours
        duration = timedelta(hours=2)
        end_time = res_time + duration

        # 1. Find a Table
        target_table = None
        
        if table_id:
            # Check specific table
            table = Table.objects.get(id=table_id)
            conflict = Reservation.objects.filter(
                table=table,
                reservation_time__lt=end_time, # Starts before this one ends
                reservation_time__gt=res_time - duration # Ends after this one starts
            ).exists()
            
            if conflict:
                return Response({"error": f"Table {table.name} is already booked for this time."}, status=400)
            target_table = table
        else:
            # Auto-Assign: Find any free table with capacity (assuming all tables fit 4 for MVP)
            all_tables = Table.objects.filter(restaurant=restaurant)
            for t in all_tables:
                conflict = Reservation.objects.filter(
                    table=t,
                    reservation_time__lt=end_time,
                    reservation_time__gt=res_time - duration
                ).exists()
                if not conflict:
                    target_table = t
                    break
            
            if not target_table:
                return Response({"error": "No tables available for this time slot."}, status=400)

        # 2. Book It
        Reservation.objects.create(
            restaurant=restaurant,
            table=target_table,
            customer_name=data.get('name'),
            customer_phone=data.get('phone'),
            reservation_time=res_time,
            guests=guests
        )
        
        return Response({
            "status": "confirmed", 
            "table": target_table.name, 
            "time": res_time_str
        })

    except Exception as e:
        return Response({"error": str(e)}, status=400)