from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from ..models import Comment, Group, Post

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
        image = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.test_image = SimpleUploadedFile(
            name='small.gif',
            content=image,
            content_type='image/gif'
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
            group=cls.group,
            image=cls.test_image
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
            'text': 'Новый тестовый текст',
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

    def test_comment_authorized_client(self):
        """Комментировать посты может только авторизованный пользователь."""
        comments_count = Comment.objects.count()
        form_data = {
            'text': 'Тестовый комментарий'}
        response = self.authorized_client.post(
            reverse('posts:add_comment', kwargs={'post_id': self.post.id}),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(
            response, reverse('posts:post_detail',
                              kwargs={'post_id': self.post.id}))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        # после успешной отправки комментарий появляется на странице поста
        self.assertEqual(Comment.objects.count(), comments_count + 1)
        first_comment = Comment.objects.first()
        self.assertEqual(first_comment.text, form_data['text'])
        self.assertEqual(first_comment.post, self.post)
        self.assertEqual(first_comment.author, self.user)

    def test_comment_guest_client(self):
        """Проверяем редирект неавторизованного пользователя
        при попытке создать комментарий."""
        form_data = {
            'text': 'Тестовый комментарий'}
        response = self.guest_client.post(
            reverse('posts:add_comment',
                    kwargs={'post_id': self.post.id}),
            data=form_data,
            follow=True
        )
        auth = reverse('users:login')
        add_comment = reverse('posts:add_comment',
                              kwargs={'post_id': self.post.id})
        self.assertRedirects(response, (f'{auth}?next={add_comment}'))
