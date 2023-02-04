import shutil
import tempfile
from http import HTTPStatus

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Comment, Follow, Group, Post

User = get_user_model()


class PostPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username='auth')
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
        cls.INDEX = 'posts:index'
        cls.GROUP = 'posts:group_posts'
        cls.PROFILE = 'posts:profile'
        cls.POST_ID = 'posts:post_detail'
        cls.POST_ID_EDIT = 'posts:post_edit'
        cls.CREATE = 'posts:post_create'
        cls.templates_pages_names = {
            reverse(cls.INDEX): 'posts/index.html',
            reverse(
                cls.GROUP, kwargs={'slug': cls.group.slug}
            ): 'posts/group_list.html',
            reverse(
                cls.PROFILE, kwargs={'username': cls.post.author}
            ): 'posts/profile.html',
            reverse(
                cls.POST_ID, kwargs={'post_id': cls.post.id}
            ): 'posts/post_detail.html',
            reverse(
                cls.POST_ID_EDIT, kwargs={'post_id': cls.post.id}
            ): 'posts/create_post.html',
            reverse(cls.CREATE): 'posts/create_post.html',
        }

    def setUp(self):
        # Создаем неавторизованный клиент
        self.guest_client = Client()
        # Создаем второй клиент
        self.authorized_client = Client()
        # Авторизуем пользователя
        self.authorized_client.force_login(self.user)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        # Проверяем, что вызывается соответствующий HTML-шаблон
        for template, reverse_name in self.templates_pages_names.items():
            with self.subTest(template=template):
                response = self.authorized_client.get(template)
                self.assertTemplateUsed(response, reverse_name)

    def test_index_page_show_correct_context(self):
        """Шаблон index сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse(self.INDEX))
        object_list = list(Post.objects.all())
        self.assertEqual(list(response.context['page_obj']), object_list)

    def test_group_list_page_show_correct_context(self):
        """Шаблон group_list сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse(self.GROUP, kwargs={'slug': self.group.slug}))
        object_list = list(Post.objects.filter(group_id=self.group.id))
        self.assertEqual(list(response.context['page_obj']), object_list)

    def test_profile_page_show_correct_context(self):
        """Шаблон profile сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse(self.PROFILE, args={self.user.username}))
        object_list = list(Post.objects.filter(author_id=self.user.id))
        self.assertEqual(list(response.context['page_obj']), object_list)

    def test_post_detail_page_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse(self.POST_ID, kwargs={'post_id': self.post.id}))
        post_object = response.context.get('post')
        self.assertEqual(post_object.text, self.post.text)
        self.assertEqual(post_object.author, self.post.author)
        self.assertEqual(post_object.group, self.post.group)

    def test_create_post_page_for_post_id_edit_show_correct_context(self):
        """Шаблон create_post сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse(self.POST_ID_EDIT, kwargs={'post_id': self.post.id})
        )
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.models.ModelChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context['form'].fields[value]
                self.assertIsInstance(form_field, expected)

    def test_create_post_page_for_create_show_correct_context(self):
        """Шаблон create_post сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse(self.CREATE))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.models.ModelChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context['form'].fields[value]
                self.assertIsInstance(form_field, expected)

    def test_check_group_in_pages(self):
        """Проверяем создание поста на страницах с выбранной группой"""
        form_fields = {
            reverse(self.INDEX): Post.objects.get(group=self.post.group),
            reverse(
                self.GROUP, kwargs={'slug': self.group.slug}
            ): Post.objects.get(group=self.post.group),
            reverse(
                'posts:profile', kwargs={'username': self.post.author}
            ): Post.objects.get(group=self.post.group),
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                response = self.authorized_client.get(value)
                form_field = response.context['page_obj']
                self.assertIn(expected, form_field)

    def test_check_group_not_in_mistake_group_list_page(self):
        """Проверяем чтобы созданный Пост с группой не попап в чужую группу."""
        form_fields = {
            reverse(
                'posts:group_posts', kwargs={'slug': self.group.slug}
            ): Post.objects.exclude(group=self.post.group),
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                response = self.authorized_client.get(value)
                form_field = response.context['page_obj']
                self.assertNotIn(expected, form_field)


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        post = [Post(
                author=cls.user,
                text=f'Тестовый пост {i}',
                group=cls.group,)
                for i in range(13)]
        cls.posts = Post.objects.bulk_create(post)

    def setUp(self):
        # Создаем неавторизованный клиент
        self.guest_client = Client()
        # Создаем второй клиент
        self.authorized_client = Client()
        # Авторизуем пользователя
        self.authorized_client.force_login(self.user)

    def test_correct_page_context(self):
        '''Проверка количества постов на первой и второй странице'''
        pages = [reverse('posts:index'),
                 reverse('posts:profile',
                         kwargs={'username': f'{self.user.username}'}),
                 reverse('posts:group_posts',
                         kwargs={'slug': f'{self.group.slug}'})]
        for page in pages:
            response1 = self.authorized_client.get(page)
            response2 = self.authorized_client.get(page + '?page=2')
            count_posts1 = len(response1.context['page_obj'])
            count_posts2 = len(response2.context['page_obj'])
            self.assertEqual(count_posts1, settings.POSTS_ON_PAGE)
            self.assertEqual(count_posts2, settings.POSTS_ON_SECOND_PAGE)


TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=cls.small_gif,
            content_type='image/gif'
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый текст',
            group=cls.group,
            image=cls.uploaded
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()

    def test_image_index_page(self):
        """Картинка передается на страницу index."""
        response = self.guest_client.get(reverse('posts:index'))
        obj = response.context['page_obj'][0]
        self.assertEqual(obj.image, self.post.image)

    def test_image_profile_page(self):
        """Картинка передается на страницу profile."""
        response = self.guest_client.get(
            reverse('posts:profile', args={self.user.username}))
        obj = response.context['page_obj'][0]
        self.assertEqual(obj.image, self.post.image)

    def test_image_group_posts_page(self):
        """Картинка передается на страницу group_posts."""
        response = self.guest_client.get(
            reverse('posts:group_posts', kwargs={'slug': self.group.slug}),
        )
        obj = response.context['page_obj'][0]
        self.assertEqual(obj.image, self.post.image)

    def test_image_post_detail_page(self):
        """Картинка передается на страницу post_detail."""
        response = self.guest_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.id})
        )
        obj = response.context['post']
        self.assertEqual(obj.image, self.post.image)

    def test_image_in_page(self):
        """Пост с картинкой создается в БД"""
        self.assertTrue(
            Post.objects.filter(text='Тестовый текст',
                                image='posts/small.gif').exists())


class CommentTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username='auth')
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
        cls.guest_client = Client()
        cls.authorized_client = Client()
        cls.authorized_client.force_login(cls.user)

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
        self.assertTrue(
            Comment.objects.filter(text='Тестовый комментарий').exists())


class CacheViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username='auth')
        Post.objects.create(
            text='Тестовый пост',
            author=cls.user)

    def setUp(self):
        self.guest_client = Client()

    def test_cache_index_pages(self):
        """Проверяем работу кэша главной страницы."""
        response_1 = self.client.get('posts:index')
        Post.objects.create(
            text='Новый тестовый пост',
            author=self.user)
        Post.objects.get(id=1).delete()
        response_2 = self.client.get('posts:index')
        self.assertEqual(
            response_1.content,
            response_2.content
        )


class FollowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='author')
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост')

    def setUp(self):
        # не авторизованный пользователь
        self.guest_client = Client()
        # авторизованный пользователь 1
        self.user_1 = User.objects.create_user(username='auth1')
        self.authorized_client_1 = Client()
        self.authorized_client_1.force_login(self.user_1)
        # авторизованный пользователь 2
        self.user_2 = User.objects.create_user(username='auth2')
        self.authorized_client_2 = Client()
        self.authorized_client_2.force_login(self.user_2)
        # авторизованный пользователь 3
        self.user_3 = User.objects.create_user(username='auth3')
        self.authorized_client_3 = Client()
        self.authorized_client_3.force_login(self.user_3)

    def test_follow(self):
        """Проверка подписки авторизованного пользователя
        на других пользователей."""
        posts_count = Follow.objects.filter(user=self.user_1).count()
        response = self.authorized_client_1.post(
            reverse('posts:profile_follow', kwargs={
                'username': self.user_2})
        )
        self.assertRedirects(response, reverse(
            'posts:profile', kwargs={
                'username': self.user_2})
        )
        posts_count_2 = Follow.objects.filter(user=self.user_1).count()
        self.assertEqual(posts_count_2, posts_count + 1)
        response = self.authorized_client_1.post(
            reverse('posts:profile_unfollow', kwargs={
                'username': self.user_2})
        )
        posts_count_2 = Follow.objects.filter(user=self.user_1).count()
        self.assertEqual(posts_count_2, posts_count)

    def test_unfollow(self):
        """Проверяем что авторизованный пользователь может удалять
        подписки."""
        Follow.objects.create(user=self.user_1,
                              author=self.user_2)
        posts_count = Follow.objects.filter(user=self.user_1).count()
        response = self.authorized_client_1.post(
            reverse('posts:profile_unfollow', kwargs={
                'username': self.user_2})
        )
        self.assertRedirects(response, reverse(
            'posts:profile', kwargs={
                'username': self.user_2})
        )
        posts_count_2 = Follow.objects.filter(user=self.user_1).count()
        self.assertEqual(posts_count_2, posts_count - 1)

    def test_new_post(self):
        """Проверяем что новая запись пользователя появляется в ленте тех,
        кто на него подписан и не появляется в ленте тех, кто не подписан."""
        Follow.objects.create(user=self.user_1,
                              author=self.user_2)
        response = self.authorized_client_3.get(reverse('posts:follow_index'))
        posts_count = len(response.context['page_obj'])
        self.assertEqual(posts_count, 0)
        response = self.authorized_client_1.get(reverse('posts:follow_index'))
        posts_count = len(response.context['page_obj'])
        self.assertEqual(posts_count, 0)
        self.authorized_client_2.post(
            reverse('posts:post_create'),
            data={'text': 'Тестовый пост 2'},
            follow=True
        )
        response = self.authorized_client_1.get(reverse('posts:follow_index'))
        posts_count_2 = len(response.context['page_obj'])
        self.assertEqual(posts_count_2, 1)
        response = self.authorized_client_3.get(reverse('posts:follow_index'))
        posts_count = len(response.context['page_obj'])
        self.assertEqual(posts_count, 0)
