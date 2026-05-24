import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Используем SQLite с постоянным путём на Render
# Render позволяет запись в /tmp и в директорию проекта
import tempfile
import os

# Создаём директорию для базы данных, если её нет
db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(db_dir, exist_ok=True)

db_path = os.path.join(db_dir, 'recipes.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print(f"Using database at: {db_path}")

db = SQLAlchemy(app)

# Модель данных
class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    prep_time = db.Column(db.Integer, default=30)
    category = db.Column(db.String(100), default='Основное блюдо')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Recipe {self.title}>'

# Создаём таблицы
with app.app_context():
    db.create_all()
    print("Database tables created successfully")

# Маршруты
@app.route('/')
def index():
    recipes = Recipe.query.order_by(Recipe.created_at.desc()).all()
    categories = [cat[0] for cat in db.session.query(Recipe.category).distinct().all() if cat[0]]
    return render_template('index.html', recipes=recipes, categories=categories)

@app.route('/recipe/<int:id>')
def recipe_detail(id):
    recipe = Recipe.query.get_or_404(id)
    return render_template('recipe_detail.html', recipe=recipe)

@app.route('/add', methods=['GET', 'POST'])
def add_recipe():
    if request.method == 'POST':
        try:
            recipe = Recipe(
                title=request.form['title'],
                description=request.form['description'],
                ingredients=request.form['ingredients'],
                instructions=request.form['instructions'],
                prep_time=int(request.form.get('prep_time', 30)),
                category=request.form.get('category', 'Основное блюдо')
            )
            db.session.add(recipe)
            db.session.commit()
            flash(f'Рецепт "{recipe.title}" успешно добавлен!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
            return redirect(url_for('add_recipe'))
    return render_template('add_recipe.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_recipe(id):
    recipe = Recipe.query.get_or_404(id)
    if request.method == 'POST':
        try:
            recipe.title = request.form['title']
            recipe.description = request.form['description']
            recipe.ingredients = request.form['ingredients']
            recipe.instructions = request.form['instructions']
            recipe.prep_time = int(request.form.get('prep_time', 30))
            recipe.category = request.form.get('category', 'Основное блюдо')
            db.session.commit()
            flash(f'Рецепт "{recipe.title}" обновлен!', 'success')
            return redirect(url_for('recipe_detail', id=recipe.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
            return redirect(url_for('edit_recipe', id=recipe.id))
    return render_template('edit_recipe.html', recipe=recipe)

@app.route('/delete/<int:id>')
def delete_recipe(id):
    recipe = Recipe.query.get_or_404(id)
    title = recipe.title
    db.session.delete(recipe)
    db.session.commit()
    flash(f'Рецепт "{title}" удален', 'info')
    return redirect(url_for('index'))

@app.route('/category/<category>')
def category_filter(category):
    recipes = Recipe.query.filter_by(category=category).all()
    categories = [cat[0] for cat in db.session.query(Recipe.category).distinct().all() if cat[0]]
    return render_template('index.html', recipes=recipes, categories=categories, current_category=category)

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
    categories = [cat[0] for cat in db.session.query(Recipe.category).distinct().all() if cat[0]]
    return render_template('index.html', recipes=recipes, categories=categories, search_query=query)

# Health check для Render
@app.route('/health')
def health():
    return {"status": "healthy"}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
