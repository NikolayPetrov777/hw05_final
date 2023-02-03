from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from ..models import Group, Post

User = get_user_model()


class PostPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username='auth')
        cls.guest_client = Client()
        cls.authorized_client = Client()
        cls.authorized_client.force_login(cls.user)
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
            group=cls.group,
        )

    def test_create_post(self):
        """Валидная форма создает запись в Post."""
        # Подсчитаем количество записей в Post
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый пост',
            'group': self.group.id,
        }
        # Отправляем POST-запрос
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        # Проверяем редирект
        self.assertRedirects(response, reverse('posts:profile',
                             kwargs={'username': self.user.username}))
        # Проверяем, увеличилось ли число постов
        self.assertEqual(Post.objects.count(), posts_count + 1)
        # Проверяем, что создалась запись
        last_object = Post.objects.first()
        self.assertEqual(self.post.text, last_object.text)
        self.assertEqual(self.post.group, last_object.group)
        self.assertEqual(self.post.author, last_object.author)

    def test_create_post(self):
        """Валидная форма создает запись в Post."""
        # Подсчитаем количество записей в Post
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый пост',
            'group': self.group.id,
        }
        # Отправляем POST-запрос
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        # Проверяем редирект
        self.assertRedirects(response, reverse('posts:profile',
                             kwargs={'username': self.user.username}))
        # Проверяем, увеличилось ли число постов
        self.assertEqual(Post.objects.count(), posts_count + 1)
        # Проверяем, что создалась запись
        last_object = Post.objects.first()
        self.assertEqual(self.post.text, last_object.text)
        self.assertEqual(self.post.group, last_object.group)
        self.assertEqual(self.post.author, last_object.author)

    def test_guest_client_create_post(self):
        """Проверяем создание записи в Post."""
        # Подсчитаем количество записей в Post
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый пост из формы',
            'group': self.group.id,
        }
        auth = reverse('users:login')
        create = reverse('posts:post_create')
        # Отправляем POST-запрос
        response = self.guest_client.post(
            create,
            data=form_data,
            follow=True
        )
        # Убедимся, что запись в базе данных не создалась:
        # сравним количество записей в Post до и после отправки формы
        self.assertEqual(Post.objects.count(), posts_count)
        # Проверим, что ничего не упало и страница отдаёт код 200
        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Проверим редирект неавторизованного пользователя
        self.assertRedirects(response, (f'{auth}?next={create}'))

    def test_post_edit(self):
        """Валидная форма создает запись в Post."""
        form_data = {
            'text': 'Тестовый текст новый',
            'group': self.group.id,
        }
        # Отправляем POST-запрос
        self.authorized_client.post(
            reverse('posts:post_edit', kwargs={'post_id': self.post.id}),
            data=form_data,
            follow=True
        )
        # Проверяем, что происходит изменение в тексте поста
        last_object = Post.objects.first()
        self.assertNotEqual(self.post.text, last_object.text)
        self.assertEqual(self.post.group, last_object.group)
        self.assertEqual(self.post.author, last_object.author)

    def test_guest_client_post_edit(self):
        """Проверяем редирект неавторизованного пользователя."""
        response = self.guest_client.post(
            reverse('posts:post_edit',
                    kwargs={'post_id': self.post.id}),
            follow=True
        )
        auth = reverse('users:login')
        post_edit = reverse('posts:post_edit',
                            kwargs={'post_id': self.post.id})
        self.assertRedirects(response, (f'{auth}?next={post_edit}'))
