from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Настройка базы данных: PostgreSQL на Render или SQLite для локальной разработки
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    # Render.com использует postgres://, но SQLAlchemy требует postgresql://
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///recipes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Модель для рецептов
class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    prep_time = db.Column(db.Integer, default=30)
    category = db.Column(db.String(50), default="Основное блюдо")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Recipe {self.title}>'

# Создание таблиц (безопасно для обоих типов БД)
with app.app_context():
    db.create_all()

# Главная страница
@app.route('/')
def index():
    recipes = Recipe.query.order_by(Recipe.created_at.desc()).all()
    categories = db.session.query(Recipe.category).distinct().all()
    categories = [cat[0] for cat in categories]
    return render_template('index.html', recipes=recipes, categories=categories)

# Просмотр рецепта
@app.route('/recipe/<int:id>')
def recipe_detail(id):
    recipe = Recipe.query.get_or_404(id)
    return render_template('recipe_detail.html', recipe=recipe)

# Добавление рецепта
@app.route('/add', methods=['GET', 'POST'])
def add_recipe():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        ingredients = request.form.get('ingredients')
        instructions = request.form.get('instructions')
        prep_time = request.form.get('prep_time', 30)
        category = request.form.get('category')
        
        if not title or not description or not ingredients or not instructions:
            flash('Пожалуйста, заполните все поля!', 'danger')
            return redirect(url_for('add_recipe'))
        
        recipe = Recipe(
            title=title,
            description=description,
            ingredients=ingredients,
            instructions=instructions,
            prep_time=int(prep_time),
            category=category
        )
        
        db.session.add(recipe)
        db.session.commit()
        
        flash(f'Рецепт "{title}" успешно добавлен!', 'success')
        return redirect(url_for('index'))
    
    return render_template('add_recipe.html')

# Редактирование рецепта
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_recipe(id):
    recipe = Recipe.query.get_or_404(id)
    
    if request.method == 'POST':
        recipe.title = request.form.get('title')
        recipe.description = request.form.get('description')
        recipe.ingredients = request.form.get('ingredients')
        recipe.instructions = request.form.get('instructions')
        recipe.prep_time = int(request.form.get('prep_time', 30))
        recipe.category = request.form.get('category')
        
        db.session.commit()
        flash(f'Рецепт "{recipe.title}" успешно обновлен!', 'success')
        return redirect(url_for('recipe_detail', id=recipe.id))
    
    return render_template('edit_recipe.html', recipe=recipe)

# Удаление рецепта
@app.route('/delete/<int:id>')
def delete_recipe(id):
    recipe = Recipe.query.get_or_404(id)
    title = recipe.title
    db.session.delete(recipe)
    db.session.commit()
    flash(f'Рецепт "{title}" удален!', 'info')
    return redirect(url_for('index'))

# Фильтрация по категориям
@app.route('/category/<category>')
def category_filter(category):
    recipes = Recipe.query.filter_by(category=category).all()
    categories = db.session.query(Recipe.category).distinct().all()
    categories = [cat[0] for cat in categories]
    return render_template('index.html', recipes=recipes, categories=categories, current_category=category)

# Поиск рецептов
@app.route('/search')
def search():
    query = request.args.get('q', '')
    if query:
        recipes = Recipe.query.filter(
            (Recipe.title.contains(query)) | 
            (Recipe.description.contains(query)) |
            (Recipe.ingredients.contains(query))
        ).all()
    else:
        recipes = []
    
    return render_template('index.html', recipes=recipes, search_query=query)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
