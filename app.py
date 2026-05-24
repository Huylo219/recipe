import os
import sys
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

# Создаём приложение
app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Настройка базы данных для Render (используем /tmp для SQLite)
# Если есть DATABASE_URL (PostgreSQL), используем её, иначе SQLite в /tmp
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # Для Render используем /tmp - единственная директория, доступная для записи
    db_path = os.path.join(tempfile.gettempdir(), 'recipes.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    print(f"Using SQLite database at: {db_path}")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице'

# Декоратор для проверки прав администратора
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# ========== МОДЕЛИ ДАННЫХ ==========

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    recipes = db.relationship('Recipe', backref='author', lazy=True)
    reviews = db.relationship('Review', backref='author', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    prep_time = db.Column(db.Integer, default=30)
    category = db.Column(db.String(100), default='Основное блюдо')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reviews = db.relationship('Review', backref='recipe', lazy=True, cascade='all, delete-orphan')
    
    def average_rating(self):
        if self.reviews:
            return sum(r.rating for r in self.reviews) / len(self.reviews)
        return 0
    
    def rating_count(self):
        return len(self.reviews)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# ========== ЗАГРУЗЧИК ПОЛЬЗОВАТЕЛЯ ==========

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ========== СОЗДАНИЕ АДМИНИСТРАТОРА ==========

def create_admin():
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✅ Администратор создан: admin / admin123")
        else:
            print("ℹ️ Администратор уже существует")

# ========== МАРШРУТЫ АВТОРИЗАЦИИ ==========

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Пароли не совпадают!', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует!', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует!', 'danger')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Регистрация успешна! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash(f'Добро пожаловать, {user.username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

# ========== ОСНОВНЫЕ МАРШРУТЫ ==========

@app.route('/')
def index():
    recipes = Recipe.query.order_by(Recipe.created_at.desc()).all()
    categories = db.session.query(Recipe.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    return render_template('index.html', recipes=recipes, categories=categories)

@app.route('/recipe/<int:id>')
def recipe_detail(id):
    recipe = Recipe.query.get_or_404(id)
    reviews = Review.query.filter_by(recipe_id=id).order_by(Review.created_at.desc()).all()
    return render_template('recipe_detail.html', recipe=recipe, reviews=reviews)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_recipe():
    if request.method == 'POST':
        try:
            recipe = Recipe(
                title=request.form['title'],
                description=request.form['description'],
                ingredients=request.form['ingredients'],
                instructions=request.form['instructions'],
                prep_time=int(request.form.get('prep_time', 30)),
                category=request.form.get('category', 'Основное блюдо'),
                user_id=current_user.id
            )
            db.session.add(recipe)
            db.session.commit()
            flash(f'✨ Рецепт "{recipe.title}" успешно добавлен!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
            return redirect(url_for('add_recipe'))
    return render_template('add_recipe.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_recipe(id):
    recipe = Recipe.query.get_or_404(id)
    
    if not current_user.is_admin and recipe.user_id != current_user.id:
        flash('У вас нет прав для редактирования этого рецепта', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            recipe.title = request.form['title']
            recipe.description = request.form['description']
            recipe.ingredients = request.form['ingredients']
            recipe.instructions = request.form['instructions']
            recipe.prep_time = int(request.form.get('prep_time', 30))
            recipe.category = request.form.get('category', 'Основное блюдо')
            db.session.commit()
            flash(f'📝 Рецепт "{recipe.title}" обновлен!', 'success')
            return redirect(url_for('recipe_detail', id=recipe.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
            return redirect(url_for('edit_recipe', id=recipe.id))
    return render_template('edit_recipe.html', recipe=recipe)

@app.route('/delete/<int:id>')
@login_required
def delete_recipe(id):
    recipe = Recipe.query.get_or_404(id)
    
    if not current_user.is_admin and recipe.user_id != current_user.id:
        flash('У вас нет прав для удаления этого рецепта', 'danger')
        return redirect(url_for('index'))
    
    title = recipe.title
    db.session.delete(recipe)
    db.session.commit()
    flash(f'🗑️ Рецепт "{title}" удален', 'info')
    return redirect(url_for('index'))

@app.route('/add_review/<int:recipe_id>', methods=['POST'])
@login_required
def add_review(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    try:
        rating = int(request.form.get('rating', 5))
        comment = request.form.get('comment', '')
        
        if not comment:
            flash('Пожалуйста, оставьте комментарий!', 'danger')
            return redirect(url_for('recipe_detail', id=recipe_id))
        
        review = Review(
            rating=rating,
            comment=comment,
            recipe_id=recipe_id,
            user_id=current_user.id
        )
        db.session.add(review)
        db.session.commit()
        flash('💬 Спасибо за ваш отзыв!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при добавлении отзыва: {str(e)}', 'danger')
    
    return redirect(url_for('recipe_detail', id=recipe_id))

@app.route('/delete_review/<int:review_id>')
@login_required
def delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    
    if not current_user.is_admin and review.user_id != current_user.id:
        flash('У вас нет прав для удаления этого отзыва', 'danger')
        return redirect(url_for('recipe_detail', id=review.recipe_id))
    
    recipe_id = review.recipe_id
    db.session.delete(review)
    db.session.commit()
    flash('Отзыв удален', 'info')
    return redirect(url_for('recipe_detail', id=recipe_id))

@app.route('/category/<category>')
def category_filter(category):
    recipes = Recipe.query.filter_by(category=category).all()
    categories = db.session.query(Recipe.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
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
    categories = db.session.query(Recipe.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    return render_template('index.html', recipes=recipes, categories=categories, search_query=query)

@app.route('/admin')
@admin_required
def admin_panel():
    users = User.query.all()
    recipes = Recipe.query.all()
    reviews = Review.query.all()
    return render_template('admin_panel.html', users=users, recipes=recipes, reviews=reviews)

@app.route('/admin/delete_user/<int:id>')
@admin_required
def admin_delete_user(id):
    user = User.query.get_or_404(id)
    if user.is_admin:
        flash('Нельзя удалить администратора!', 'danger')
        return redirect(url_for('admin_panel'))
    
    for recipe in user.recipes:
        db.session.delete(recipe)
    db.session.delete(user)
    db.session.commit()
    flash(f'Пользователь {user.username} удален', 'info')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_recipe/<int:id>')
@admin_required
def admin_delete_recipe(id):
    recipe = Recipe.query.get_or_404(id)
    db.session.delete(recipe)
    db.session.commit()
    flash(f'Рецепт "{recipe.title}" удален администратором', 'info')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_review/<int:id>')
@admin_required
def admin_delete_review(id):
    review = Review.query.get_or_404(id)
    db.session.delete(review)
    db.session.commit()
    flash('Отзыв удален администратором', 'info')
    return redirect(url_for('admin_panel'))

@app.route('/health')
def health():
    return {"status": "healthy"}, 200

# ========== ЗАПУСК ==========

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin()
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
