from rest_framework import serializers
from adora.models import Category, Product, ProductImage, Brand, Comment, Matrial, Car
from django.core.exceptions import ValidationError
from django.core.exceptions import ObjectDoesNotExist


class CarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Car
        exclude = ('created_date', 'updated_date')
  
# class CategorySeriali


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        # fields = ('id', 'alt', 'image_url', 'product')
        exclude = ('created_date', 'updated_date')
        
class CategoryWhitChildrenSerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields =['id', 'name', 'image', 'alt', 'parent', 'children']
      
    def get_parent(self, obj):
        # If parent exists, return its serialized data using the same serializer
        if obj.parent:
            # return CategorySerializer(obj.parent).data
            return obj.parent.name
        return None
    
    def get_children(self, obj):
        children = obj.children.all()
        return CategoryWhitChildrenSerializer(children, many=True).data

        
class CategorySerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()


    class Meta:
        model = Category
        fields =['id', 'name', 'image', 'alt', 'parent',]
      
    def get_parent(self, obj):
        # If parent exists, return its serialized data using the same serializer
        if obj.parent:
            # return CategorySerializer(obj.parent).data
            return obj.parent.name
        return None
    
        
        
class SimilarProductsSerializer(serializers.ModelSerializer):
    # category = serializers.SerializerMethodField(read_only=True)
    # material = serializers.SerializerMethodField(read_only=True)
    compatible_cars = serializers.SerializerMethodField(read_only=True)
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
                #   'material',
                #   'category',
                  'compatible_cars',
                  'brand',
                  'images',
                #   'description',
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
    
    
class MaterialSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='material_name')
    class Meta:
        model = Matrial
        fields = ['id', 'name']


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        # fields = '__all__'
        exclude = ['created_date', 'updated_date', 'alt']
 
     
class CommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField(read_only=True)  # Marking user as read-only with custom logic

    class Meta:
        model = Comment
        fields = ['id','user',  'product', 'parent', 'text', 'rating','buy_suggest', 'created_date', 'updated_date', 'replies']
        

    def get_replies(self, obj):
        replies = obj.replies.all()  # Fetch all replies to the current comment
        return CommentSerializer(replies, many=True).data  # Serialize each reply

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value
    
    def get_user(self,obj):
        # profile = getattr(obj.user,'profile', None)
        # if profile and profile.first_name:
        #     return f"{obj.user.profile.first_name} {obj.user.profile.last_name}"
        
        return obj.user.id


class ProductSearchSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    discounted_price = serializers.SerializerMethodField(read_only=True)
    discounted_wallet = serializers.SerializerMethodField(read_only=True)
    wallet_discount_percent = serializers.CharField(source='wallet_discount')
    main_category = CategorySerializer(read_only=True, source='category')
    compatible_cars = serializers.SerializerMethodField(read_only=True)
    brand= BrandSerializer(read_only=True)




    class Meta:
        model = Product
        fields = ['id',
                'custom_id',
                  'fa_name', 
                  'en_name', 
                  'price',
                  'price_discount_percent',
                  'discounted_price',
                  'wallet_discount_percent',
                  'discounted_wallet',
                  'count',
                  'install_location',
                  'guarantee',
                  'new',
                  'main_category',
                  'compatible_cars',
                  'brand',
                  'images',
                  'buyer',
                  'customer_point',

                  ]
        
    def get_discounted_price(self,obj):
        return obj.price - ((obj.price * obj.price_discount_percent) / 100)
    
    def get_discounted_wallet(self, obj):
        return (obj.price * obj.wallet_discount) / 100

    def get_compatible_cars(self, obj):
        return [{
                "id": car.id,
                "fa_name":car.fa_name,
                 "image_url": car.image,
                 "image_alt": car.alt} for car in obj.compatible_cars.all()]
    

class ProductRetrieveSerializer(serializers.ModelSerializer):
    # main_category = serializers.CharField(source='category.fa_name', read_only=True)
    # minor_category = serializers.CharField(source='material.material_name', read_only=True)
    # comments = CommentSerializer(read_only=True, many=True)
    comments = serializers.SerializerMethodField()
    main_category = CategorySerializer(read_only=True, source='category')
    # minor_category = MaterialSerializer(read_only=True, source='material')
    compatible_cars = serializers.SerializerMethodField(read_only=True)
    # image = serializers.SerializerMethodField(read_only=True)
    discounted_price = serializers.SerializerMethodField(read_only=True)
    discounted_wallet = serializers.SerializerMethodField(read_only=True)
    # brand= serializers.SerializerMethodField(read_only=True)
    brand= BrandSerializer(read_only=True)
    similar_products = SimilarProductsSerializer(many=True)
    images = ProductImageSerializer(many=True, read_only=True)
    wallet_discount_percent = serializers.CharField(source='wallet_discount')


    
    class Meta:
        model = Product
        fields = ['id',
                   'custom_id',
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
                  'main_category',
                  'compatible_cars',
                  'similar_products',
                  'brand',
                  'images',
                  'title_description',
                  'packing_description',
                  'shopping_description',
                  'buyer',
                  'customer_point',
                  'comments', 
             
                  ]
        
        
    # def get_brand(self, obj):
    #     return {'id': obj.brand.id, 'name': obj.brand.name, 'image_url': obj.brand.image, 'alt': obj.brand.alt}
        
        
    def get_comments(self, obj):
        comments = obj.comments.filter(parent__isnull=True)
        return CommentSerializer(comments, many=True).data
        
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


class ProductListSerializer(serializers.ModelSerializer):
    main_category = CategorySerializer(read_only=True, source='category')
    # minor_category = MaterialSerializer(read_only=True, source='material')
    compatible_cars = serializers.SerializerMethodField(read_only=True)
    # image = serializers.SerializerMethodField(read_only=True)
    discounted_price = serializers.SerializerMethodField(read_only=True)
    discounted_wallet = serializers.SerializerMethodField(read_only=True)
    comments = serializers.SerializerMethodField()
    # brand= serializers.SerializerMethodField(read_only=True)
    brand = BrandSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    wallet_discount_percent = serializers.CharField(source='wallet_discount')


    
    class Meta:
        model = Product
        fields = ['id',
                  'custom_id',
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
                  'main_category',
                  'compatible_cars',
                  'brand',
                  'images',
                  'title_description',
                  'packing_description',
                  'shopping_description',
                  'buyer',
                  'customer_point',
                  'comments'
   
                  ]
        
        
        
    # def get_brand(self, obj):
    #     return {'id': obj.brand.id, 'name': obj.brand.name, 'image_url': obj.brand.image, 'alt': obj.brand.alt}
        
    def get_comments(self, obj):
        comments = obj.comments.filter(parent__isnull=True)
        return CommentSerializer(comments, many=True).data
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


    
    # def validate(self, data):
    #     product = data.get('product')
    #     if product and Comment.objects.filter(product=product).count() >= 5:
    #         raise serializers.ValidationError("A product cannot have more than 5 comments")
    #     return datam