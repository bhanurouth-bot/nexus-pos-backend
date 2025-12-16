from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from restaurant import views  # Ensure views are imported

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 1. API URLs (Android & Data Fetching)
    path('api/', include('restaurant.urls')),
    
    # 2. WEB DASHBOARDS (Root Access)
    path('inventory/', views.inventory_dashboard),
    path('kitchen-display/', views.kitchen_dashboard),
    path('cashier-display/', views.cashier_dashboard),
    
    # --- ADD THIS LINE ---
    path('analytics/', views.analytics_dashboard),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)