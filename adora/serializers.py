from rest_framework import serializers
from adora.models import Category, Product, ProductImage, Brand
from django.core.exceptions import ValidationError


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = '__all__'

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields =['image', 'alt']
        
        
class SimilarProductsSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField(read_only=True)
    material = serializers.SerializerMethodField(read_only=True)
    compatible_cars = serializers.SerializerMethodField(read_only=True)
    # image = serializers.SerializerMethodField(read_only=True)
    discounted_price = serializers.SerializerMethodField(read_only=True)
    discounted_wallet = serializers.SerializerMethodField(read_only=True)
    brand= serializers.SerializerMethodField(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    wallet_discount_percent = serializers.CharField(source='wallet_discount')
    
    class Meta:
        model = Product
        fields = ['id',
                  'fa_name', 
                  'en_name', 
                  'price',
                  'price_discount_percent',
                  'discounted_price',
                  'wallet_discount_percent',
                  'discounted_wallet',
                  'count',
                  'new',
                  'material',
                  'category',
                  'compatible_cars',
                  'brand',
                  'images',
                  'description',
                  'buyer',
                  'customer_point',
                  ]
        
    def get_brand(self, obj):
        return {'id': obj.brand.id, 'name': obj.brand.name, 'image_url': obj.brand.image, 'alt': obj.brand.alt}
        
    def get_category(self,obj):
        return {'id':obj.category.id, 'name':obj.category.name, 'image_url': obj.category.image, 'alt':obj.category.alt}
    
    def get_material(self,obj):
        return {"id":obj.material.id, "name": obj.material.material_name}
    
    def get_compatible_cars(self, obj):
        return [{
                "id": car.id,
                "fa_name":car.fa_name,
                 "image_url": car.image,
                 "image_alt": car.alt} for car in obj.compatible_cars.all()]
    
    def get_discounted_price(self,obj):
        return obj.price - ((obj.price * obj.price_discount_percent) / 100)
    
    def get_discounted_wallet(self, obj):
        return (obj.price * obj.wallet_discount) / 100

class ProductSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField(read_only=True)
    material = serializers.SerializerMethodField(read_only=True)
    compatible_cars = serializers.SerializerMethodField(read_only=True)
    # image = serializers.SerializerMethodField(read_only=True)
    discounted_price = serializers.SerializerMethodField(read_only=True)
    discounted_wallet = serializers.SerializerMethodField(read_only=True)
    brand= serializers.SerializerMethodField(read_only=True)
    similar_products = SimilarProductsSerializer(many=True)
    images = ProductImageSerializer(many=True, read_only=True)
    wallet_discount_percent = serializers.CharField(source='wallet_discount')


    
    class Meta:
        model = Product
        fields = ['id',
                  'fa_name', 
                  'en_name', 
                  'price',
                  'price_discount_percent',
                  'discounted_price',
                  'wallet_discount_percent',
                  'discounted_wallet',
                  'count',
                  'install_location',
                  'count_in_box',
                  'guarantee',
                  'guarantee_duration',
                  'new',
                  'material',
                  'category',
                  'compatible_cars',
                  'similar_products',
                  'brand',
                  'images',
                  'description',
                  'buyer',
                  'customer_point',
                #   'created_date',
                #   'updated_date'
                  ]
        
        
    def get_brand(self, obj):
        return {'id': obj.brand.id, 'name': obj.brand.name, 'image_url': obj.brand.image, 'alt': obj.brand.alt}
        
    def get_category(self,obj):
        return {'id':obj.category.id, 'name':obj.category.name, 'image_url': obj.category.image, 'alt':obj.category.alt}
    
    def get_material(self,obj):
        return {"id":obj.material.id, "name": obj.material.material_name}
    
    def get_compatible_cars(self, obj):
        return [{
                "id": car.id,
                "fa_name":car.fa_name,
                 "image_url": car.image,
                 "image_alt": car.alt} for car in obj.compatible_cars.all()]
    
    def get_discounted_price(self,obj):
        return obj.price - ((obj.price * obj.price_discount_percent) / 100)
    
    def get_discounted_wallet(self, obj):
        return (obj.price * obj.wallet_discount) / 100

    # def get_similar_products(self, obj):
    #     return ProductSerializer(obj.similar_products.all(), many=True).data
    

    # def validate_price(self, value):
    #     try:
    #         # Validate the price field
    #         return value
    #     except ValidationError as e:
    #         raise serializers.ValidationError("Custom error message for price validation")


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = '__all__'