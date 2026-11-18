from django.db import models
from django.db.models import Q
from django.db.models.functions import Now
from django.utils import timezone


class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "categories"
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    menu_item_id = models.AutoField(primary_key=True)
    # Can't delete a category that still has items
    category = models.ForeignKey(
        Category,
        on_delete=models.RESTRICT,
        related_name="menu_items",
        db_column="category_id",
    )
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=Now())

    class Meta:
        db_table = "menu_items"
        ordering = ["category__name", "name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gt=0),
                name="menu_items_price_check",
                violation_error_message="Price must be greater than zero.",
            ),
        ]

    def __str__(self):
        return self.name
