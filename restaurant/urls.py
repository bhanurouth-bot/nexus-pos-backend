from django.urls import path
from . import views

urlpatterns = [
    # --- APP APIs (Android) ---
    path('menu/<uuid:restaurant_id>/', views.get_restaurant_menu),
    path('tables/<uuid:restaurant_id>/', views.get_tables),
    path('waiter/login/', views.waiter_login),
    path('orders/create/', views.create_order),
    path('orders/active/<uuid:restaurant_id>/', views.get_active_orders), # New "Active Orders" API

    # --- KITCHEN API ---
    path('kitchen/orders/', views.get_kitchen_orders),
    path('orders/<int:order_id>/complete/', views.complete_order),

    # --- CASHIER API ---
    path('bill/<int:table_id>/', views.get_table_bill),
    path('settle/<int:table_id>/', views.settle_table),
    path('reservations/create/', views.make_reservation), # New Reservations API

    # --- INVENTORY API ---
    path('inventory/data/<uuid:restaurant_id>/', views.get_inventory_data),
    path('inventory/save/', views.save_recipe_connection),
    path('inventory/ingredient/add/', views.add_ingredient),
    path('inventory/update-cost/', views.update_ingredient_cost), # New Costing API

    # --- ANALYTICS DATA API (FIXED) ---
    path('analytics/data/<uuid:restaurant_id>/', views.get_analytics_data),
]