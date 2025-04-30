from django.contrib import admin
from modeltranslation.admin import TranslationAdmin
from django.utils.translation import get_language
from django.utils.safestring import mark_safe

from .models import *

admin.site.site_header = "Fruitables"


@admin.register(MyUser)
class MyUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'first_name', 'last_name')
    list_display_links = ('id', 'username')


class CategoryInline(admin.TabularInline):
    model = Category
    fields = ('name_uz', 'name_en', 'slug_uz', 'slug_en')
    prepopulated_fields = {
        'slug_uz': ('name_uz',),
        'slug_en': ('name_en',)
    }

    extra = 0


@admin.register(Departament)
class DepartamentAdmin(TranslationAdmin):
    list_display = ('id', 'name', 'slug')
    list_display_links = ('id', 'name')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [CategoryInline]

    def get_fieldsets(self, request, obj=None):
        return [("Bo'lim", {'fields': ('name_uz', 'name_en', 'slug_uz', 'slug_en')})]


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    min_num = 1
    validate_min = True


@admin.register(Product)
class ProductAdmin(TranslationAdmin):
    list_display = ('id', 'get_name', 'get_slug', 'currency', 'price', 'discount', 'quantity', 'quality', 'weight', 'category', 'get_image')
    list_display_links = ('id', 'get_name')

    fieldsets = (
        ('Asosiy ma’lumotlar', {
            'fields': ('name', 'slug', 'description'),
            'classes': ('collapse',),
        }),
        ('Qo‘shimcha ma’lumotlar', {
            'fields': [field.name for field in Product._meta.concrete_fields if field.name not in [
                'id', 'name', 'slug', 'description', 'name_uz', 'name_en', 'slug_uz', 'slug_en', 'description_uz',
                'description_en'
            ]],
        }),
    )

    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            if Category.objects.all().exists():
                kwargs['empty_label'] = 'Tanlang'
            else:
                kwargs['empty_label'] = "Mavjud emas"
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "weight" or db_field.name == "currency":
            kwargs['choices'] = db_field.get_choices(
                include_blank=True,
                blank_choice=[("", "Tanlang")]
            )
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def get_name(self, obj):
        current_language = get_language()
        if current_language == 'uz':
            return obj.name_uz
        elif current_language == 'en':
            return obj.name_en
        return obj.name

    get_name.short_description = 'Name'

    def get_slug(self, obj):
        current_language = get_language()
        if current_language == 'uz':
            return obj.slug_uz
        elif current_language == 'en':
            return obj.slug_en
        return obj.slug

    get_slug.short_description = 'Slug'

    def get_image(self, product):
        images = product.images.all()
        if images.exists():
            return mark_safe(f'<img src="{images.first().image.url}" width="50px">')
        return ''

    get_image.short_description = 'Surati'


@admin.register(Coupons)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'price', 'count', 'used_count', 'created_at', 'expires_at')
    list_display_links = ('id', 'code')
    readonly_fields = ('used_count',)


@admin.register(UserCoupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'coupon')
    list_display_links = ('id', 'user')