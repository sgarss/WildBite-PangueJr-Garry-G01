from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import CategoryForm, MenuItemForm
from .models import Category, MenuItem

staff_only = role_required(User.Role.STAFF)


# Menu grouped by category (students and staff)
@login_required
def menu_list(request):
    items = MenuItem.objects.select_related("category")
    return render(request, "menu/menu_list.html", {"items": items})


# Add (no pk) or edit a menu item
@staff_only
def item_form(request, pk=None):
    item = get_object_or_404(MenuItem, pk=pk) if pk else None
    if not Category.objects.exists():
        messages.info(request, "Add a category before adding menu items.")
        return redirect("menu:category_add")

    if request.method == "POST":
        form = MenuItemForm(request.POST, instance=item)
        if form.is_valid():
            saved = form.save()
            if item:
                messages.success(request, f'"{saved}" was updated.')
            else:
                messages.success(request, f'"{saved}" was added to the menu.')
            return redirect("menu:list")
        messages.error(request, "Please fix the errors below.")
    else:
        form = MenuItemForm(instance=item)

    return render(request, "menu/form.html", {
        "form": form,
        "title": "Edit menu item" if item else "Add menu item",
        "cancel_url": reverse("menu:list"),
    })


@staff_only
def item_delete(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)
    if request.method == "POST":
        try:
            item.delete()
        except (ProtectedError, RestrictedError):
            messages.error(
                request,
                f'"{item}" is part of existing orders, so it can\'t be deleted. Mark it unavailable instead.',
            )
        else:
            messages.success(request, f'"{item}" was deleted.')
        return redirect("menu:list")

    return render(request, "menu/confirm_delete.html", {
        "object": item,
        "kind": "menu item",
        "cancel_url": reverse("menu:list"),
    })


# Switch between available and unavailable
@staff_only
@require_POST
def item_toggle(request, pk):
    item = get_object_or_404(MenuItem, pk=pk)
    item.is_available = not item.is_available
    item.save(update_fields=["is_available"])
    state = "available" if item.is_available else "unavailable"
    messages.success(request, f'"{item}" is now {state}.')
    return redirect("menu:list")


@staff_only
def category_list(request):
    categories = Category.objects.annotate(item_count=Count("menu_items"))
    return render(request, "menu/category_list.html", {"categories": categories})


# Add (no pk) or edit a category
@staff_only
def category_form(request, pk=None):
    category = get_object_or_404(Category, pk=pk) if pk else None
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated." if category else "Category added.")
            return redirect("menu:category_list")
        messages.error(request, "Please fix the errors below.")
    else:
        form = CategoryForm(instance=category)

    return render(request, "menu/form.html", {
        "form": form,
        "title": "Edit category" if category else "Add category",
        "cancel_url": reverse("menu:category_list"),
    })


@staff_only
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        try:
            category.delete()
        except (ProtectedError, RestrictedError):
            messages.error(request, f'"{category}" still has menu items, so it can\'t be deleted.')
        else:
            messages.success(request, f'"{category}" was deleted.')
        return redirect("menu:category_list")

    return render(request, "menu/confirm_delete.html", {
        "object": category,
        "kind": "category",
        "cancel_url": reverse("menu:category_list"),
    })
