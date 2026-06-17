import json
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from .models import Todo


def todo_to_dict(todo):
    return {
        'id': todo.id,
        'title': todo.title,
        'description': todo.description,
        'completed': todo.completed,
        'created_at': todo.created_at,
        'updated_at': todo.updated_at,
    }


# --- API Views (return JSON) ---

@method_decorator(csrf_exempt, name='dispatch')
class TodoListCreateView(View):

    def get(self, request):
        todos = list(Todo.objects.all().values())
        return JsonResponse(todos, safe=False)

    def post(self, request):
        data = json.loads(request.body)
        title = data.get('title')
        if not title:
            return JsonResponse({'error': 'title is required'}, status=400)
        todo = Todo.objects.create(
            title=title,
            description=data.get('description', ''),
        )
        return JsonResponse(todo_to_dict(todo), status=201)


@method_decorator(csrf_exempt, name='dispatch')
class TodoDetailUpdateDeleteView(View):

    def get(self, request, id):
        try:
            todo = Todo.objects.get(id=id)
            return JsonResponse(todo_to_dict(todo))
        except Todo.DoesNotExist:
            return JsonResponse({'error': 'Todo not found'}, status=404)

    def put(self, request, id):
        try:
            todo = Todo.objects.get(id=id)
        except Todo.DoesNotExist:
            return JsonResponse({'error': 'Todo not found'}, status=404)
        data = json.loads(request.body)
        todo.title = data.get('title', todo.title)
        todo.description = data.get('description', todo.description)
        todo.completed = data.get('completed', todo.completed)
        todo.save()
        return JsonResponse(todo_to_dict(todo))

    def delete(self, request, id):
        try:
            todo = Todo.objects.get(id=id)
        except Todo.DoesNotExist:
            return JsonResponse({'error': 'Todo not found'}, status=404)
        todo.delete()
        return JsonResponse({'message': 'Todo deleted successfully'}, status=200)


# --- HTML Views (return rendered templates) ---

class TodoListTemplateView(View):

    def get(self, request):
        todos = Todo.objects.all()
        return render(request, 'todos/todo_list.html', {'todos': todos})


class TodoDetailTemplateView(View):

    def get(self, request, id):
        try:
            todo = Todo.objects.get(id=id)
            return render(request, 'todos/todo_detail.html', {'todo': todo})
        except Todo.DoesNotExist:
            return render(request, 'todos/todo_detail.html', {'error': 'Todo not found'}, status=404)
