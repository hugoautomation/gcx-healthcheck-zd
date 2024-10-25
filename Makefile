.PHONY: start format migrate makemigrations

start:
	@pkill -f "sass --watch" || true
	@echo "Starting Django server..."
	@ruff check --fix
	@ruff format
	@sass --watch static/scss:static/css &
	@railway run python3 manage.py runserver 8000

format:
	@echo "Formatting Python code..."
	@ruff check --fix
	@ruff format

migrate:
	@echo "Applying Django migrations..."
	@railway run python3 manage.py migrate

makemigrations:
	@echo "Making Django migrations..."
	@railway run python3 manage.py makemigrations

req:
	@echo "Installing requirements..."
	@pip3 install -r requirements.txt

stop:
	@echo "Stopping Sass watcher..."
	@pkill -f "sass --watch" || true