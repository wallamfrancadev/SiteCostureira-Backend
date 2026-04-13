from produtos.models import Category, Product
from siteinfo.models import SiteInfo

# Criar categorias
cat1, _ = Category.objects.get_or_create(
    name="Costura",
    defaults={"description": "Peças de costura artesanal"}
)
cat2, _ = Category.objects.get_or_create(
    name="Artesanato",
    defaults={"description": "Artesanatos diversos"}
)
cat3, _ = Category.objects.get_or_create(
    name="Decoração",
    defaults={"description": "Itens decorativos"}
)

# Criar produtos de exemplo
produtos = [
    {
        "name": "Almofada Artesanal Floral",
        "description": "Linda almofada com bordado floral feito à mão. Perfeita para decorar sua sala ou quarto.",
        "price": 45.90,
        "stock": 10,
        "category": cat3
    },
    {
        "name": "Toalha de Mesa Bordada",
        "description": "Toalha de mesa com bordados delicados, ideal para ocasiões especiais.",
        "price": 89.90,
        "stock": 5,
        "category": cat1
    },
    {
        "name": "Necessaire em Tecido",
        "description": "Necessaire prática e elegante, feita com tecidos de alta qualidade.",
        "price": 35.00,
        "stock": 15,
        "category": cat1
    },
    {
        "name": "Jogo Americano (4 peças)",
        "description": "Conjunto de 4 jogos americanos com acabamento impecável.",
        "price": 120.00,
        "stock": 8,
        "category": cat3
    },
    {
        "name": "Boneca de Pano",
        "description": "Boneca artesanal feita com muito carinho, perfeita para presentear.",
        "price": 65.00,
        "stock": 6,
        "category": cat2
    },
    {
        "name": "Pano de Prato Bordado",
        "description": "Conjunto de panos de prato com bordados exclusivos.",
        "price": 28.50,
        "stock": 20,
        "category": cat1
    },
]

for prod_data in produtos:
    Product.objects.get_or_create(
        name=prod_data["name"],
        defaults=prod_data
    )

# Criar informações do site
SiteInfo.objects.get_or_create(
    id=1,
    defaults={
        "site_name": "Dety Costureira & Artesanatos",
        "about": "Peças artesanais feitas com amor e dedicação.",
        "phone": "(11) 99999-9999",
        "email": "contato@detycostureira.com.br",
        "whatsapp": "5511999999999",
        "address": "São Paulo, SP",
        "instagram": "https://instagram.com/detycostureira",
        "facebook": "https://facebook.com/detycostureira"
    }
)

print("✅ Banco de dados populado com sucesso!")
print(f"📦 {Product.objects.count()} produtos criados")
print(f"📁 {Category.objects.count()} categorias criadas")
