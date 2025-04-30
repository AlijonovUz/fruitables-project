import random
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404, get_list_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required, permission_required
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.utils.translation import gettext_lazy as _
from django.utils.decorators import method_decorator
from django.core.handlers.wsgi import WSGIRequest
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.contrib.auth.mixins import *
from django.core.mail import send_mail
from django.urls import reverse_lazy
from django.contrib import messages
from datetime import datetime
from django.views import View

from .models import *
from .forms import *
from .decoratos import *
from .mixins import *


class HomeListView(ListView):
    template_name = 'index.html'
    context_object_name = 'products'

    def get_queryset(self):
        products = Product.objects.all()

        if len(products) >= 8:
            product_list = random.sample(list(products), 8)
        else:
            product_list = products

        return product_list


class ProductsByDepartment(HomeListView):
    template_name = 'shop.html'
    paginate_by = 9

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)

        department = get_object_or_404(Departament, slug=self.kwargs.get('department_slug'))
        categories = Category.objects.filter(departament=department).select_related('departament')

        products = Product.objects.filter(category__departament=department).select_related('category')
        featured_products = Product.objects.filter(category__departament=department, discount__gt=0).select_related(
            'category')

        paginator = Paginator(products, self.paginate_by)
        page_number = self.request.GET.get('page', 1)
        page_obj = paginator.page(page_number)

        context.update({
            'department': department,
            'categories': categories,
            'page_obj': page_obj,
            'featured_products': featured_products[:3],
            'all_featured_products': featured_products[3:]
        })

        return context


class ProductsByCategory(ProductsByDepartment):

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)

        department = get_object_or_404(Departament, slug=self.kwargs.get('department_slug'))
        category = get_object_or_404(Category, slug=self.kwargs.get('category_slug'))

        categories = Category.objects.filter(departament=department).select_related('departament')
        featured_products = Product.objects.filter(category=category, discount__gt=0).select_related('category')

        paginator = Paginator(
            Product.objects.filter(category=category).select_related('category'),
            self.paginate_by
        )

        page_obj = paginator.page(self.request.GET.get('page', 1))

        context.update({
            'department': department,
            'categories': categories,
            'page_obj': page_obj,
            'featured_products': featured_products[:3],
            'all_featured_products': featured_products[3:]
        })

        print(context)

        return context


class ProductDetail(LoginRequiredMixin, DetailView):
    model = Product
    template_name = 'shop-detail.html'
    slug_url_kwarg = 'product_slug'
    login_url = reverse_lazy('register')

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)

        department = get_object_or_404(Departament, slug=self.kwargs.get('department_slug'))
        category = get_object_or_404(Category, slug=self.kwargs.get('category_slug'))

        categories = Category.objects.filter(departament=department).select_related('departament')
        products = Product.objects.filter(category=category).select_related('category')
        featured_products = Product.objects.filter(category=category, discount__gt=0).select_related('category')

        context.update({
            'department': department,
            'categories': categories,
            'products': products,
            'featured_products': featured_products[:3],
            'all_featured_products': featured_products[3:]
        })

        return context


class CartAction(LoginRequiredMixin, View):
    login_url = reverse_lazy('register')

    def post(self, request, **kwargs):
        product_slug = kwargs.get('product_slug')

        try:
            product = Product.objects.get(slug=product_slug)
        except Product.DoesNotExist:
            return redirect(request.META.get('HTTP_REFERER', 'home'))

        action = request.POST.get('action')
        quantity = int(request.POST.get('quantity', 1))
        product_id = str(product.pk)

        products = request.session.get('products', {})
        total_price = Decimal(str(request.session.get('total_price', '0')))

        if action == 'minus':
            products[product_id] -= 1

            if total_price:
                total_price -= product.price
                request.session['total_price'] = str(total_price)

        elif action == 'plus':

            if products.get(product_id, 0) + 1 > product.quantity:
                product_name = product.name
                messages.error(request,
                               _("%(product_name)s mahsuloti sotuvda tugadi.") % {"product_name": product_name})
                return redirect(request.META.get('HTTP_REFERER', 'home'))
            products[product_id] += 1

            if total_price:
                total_price += product.price
                request.session['total_price'] = str(total_price)

        elif action is None:
            product_name = product.name
            if not quantity > product.quantity:
                if product_id in products:
                    messages.warning(request, _("%(product_name)s savatchaga allaqachon qo'shilgan.") % {
                        "product_name": product_name})
                else:
                    messages.success(request,
                                     _("%(product_name)s savatchaga qo'shildi.") % {"product_name": product_name})
                    products[product_id] = quantity
            else:
                messages.error(request, _("Yaroqsiz miqdor kiritildi."))
                return redirect(request.META.get('HTTP_REFERER', 'home'))

        if products[product_id] <= 0:
            products.pop(product_id)

        request.session['products'] = products
        request.session.modified = True

        return redirect(request.META.get('HTTP_REFERER', 'home'))


class DeleteCart(LoginRequiredMixin, View):
    login_url = reverse_lazy('register')

    def post(self, request, **kwargs):
        product_slug = kwargs.get('product_slug')

        product = Product.objects.get(slug=product_slug)
        products = request.session.get('products')

        if str(product.pk) in products:
            messages.warning(request,
                             _("%(product_name)s savatchadan olib tashlandi.") % {"product_name": product.name})
            products.pop(str(product.pk), None)

            for key in ['total_price', 'shipping_price', 'coupon_used', 'coupon_price']:
                request.session.pop(key, None)

        request.session['products'] = products
        request.session.modified = True

        return redirect(request.META.get('HTTP_REFERER', 'home'))


def calculate_cart_total(request, coupon=None):
    products = request.session.get('products', {})
    products_details = []
    shipping = 50000
    total = 0

    for pk, quantity in products.items():
        product = get_object_or_404(Product, pk=pk)

        price = product.get_discount_price() if product.get_discount_price() else product.price

        total_price = price * quantity
        total += total_price

        products_details.append({
            'product': product,
            'quantity': quantity,
            'total_price': total_price
        })

    if coupon:
        if products:
            try:
                coupon.apply_coupon(request.user)

                if coupon.coupon_type == 'SALE':
                    total -= coupon.price
                elif coupon.coupon_type == 'FREESHIP':
                    shipping = max(0, shipping - coupon.price)

                request.session['coupon_used'] = True
                request.session['coupon_price'] = str(coupon.price)
                request.session['total_price'] = str(total)
                request.session['shipping_price'] = str(shipping)

                messages.success(request, _('Kupon muvaffaqiyatli qo\'llandi!'))
            except ValidationError as e:
                messages.error(request, e.args[0])

    return {
        'products': products_details,
        'total': total,
        'shipping': shipping,
    }


class ApplyCoupon(LoginRequiredMixin, View):
    login_url = reverse_lazy('register')

    def post(self, request):

        coupon_code = request.POST.get('coupon')
        if not coupon_code:
            messages.error(request, _('Kupon kodi kiritilmadi!'))
            return redirect('cart')

        coupon_used = request.session.get('coupon_used')
        if coupon_used:
            messages.error(request, _('Ushbu buyurtma uchun kupon allaqachon ishlatilgan!'))
            return redirect('cart')

        coupon = Coupons.objects.filter(code=coupon_code).first()
        if not coupon:
            messages.error(request, _('Kupon kodi topilmadi!'))
            return redirect('cart')

        products = calculate_cart_total(request, coupon).get('products')
        if not products:
            messages.error(request, _('Savatingiz bo\'sh!'))
            return redirect('cart')

        return redirect('cart')


class Cart(LoginRequiredMixin, ListView):
    context_object_name = 'products'
    template_name = 'cart.html'
    login_url = reverse_lazy('login')

    def get_queryset(self):
        return []

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)

        calculate = calculate_cart_total(self.request)

        products = calculate.get('products')
        total = calculate.get('total')
        shipping = calculate.get('shipping')

        coupon_used = self.request.session.get('coupon_used')
        coupon_price = self.request.session.get('coupon_price')
        total_price = self.request.session.get('total_price')
        shipping_price = self.request.session.get('shipping_price')

        if coupon_used:
            context['total'] = total_price
            context['shipping'] = shipping_price
        else:
            context['total'] = total
            context['shipping'] = shipping

        context['products'] = products
        context['coupon_price'] = coupon_price if coupon_price else None
        return context


class LoginPageView(LoginView):
    form_class = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, _("Siz muvaffaqiyatli tizimga kirdingiz!"))
        return super().form_valid(form)


class RegisterView(LoginNoRequired, CreateView):
    model = MyUser
    form_class = RegisterForm
    success_url = reverse_lazy('login')
    template_name = "registration/register.html"
    login_url = reverse_lazy('home')

    def form_valid(self, form):
        messages.success(self.request, _("Siz muvaffaqiyatli ro'yxatdan o'tdingiz!"))
        return super().form_valid(form)


class LogoutView(LoginRequiredMixin, View):

    def get(self, request):
        logout(request)
        messages.success(self.request, _("Siz muvaffaqiyatli tizimdan chiqdingiz!"))
        return redirect('login')


class Checkout(View):
    def get(self, request):
        return render(request, 'checkout.html')


class Testimonial(View):
    def get(self, request):
        return render(request, 'testimonial.html')


class Contact(View):
    def get(self, request):
        return render(request, 'contact.html')


class NotFound(View):
    def get(self, request):
        return render(request, '404.html')
