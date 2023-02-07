import shutil
import tempfile

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Follow, Group, Post

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
            self.INDEX: None,
            self.GROUP: {'slug': self.group.slug},
            self.PROFILE: {'username': self.post.author},
        }
        for key, value in form_fields.items():
            with self.subTest():
                response = self.authorized_client.get(
                    reverse(key, kwargs=value)
                )
                expected_post = Post.objects.get(group=self.post.group)
                self.assertContains(response, expected_post)

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
            Post.objects.filter(text=self.post.text,
                                image='posts/small.gif').exists())


class CacheViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username='auth')
        Post.objects.create(
            text='Тестовый пост',
            author=cls.user)
        cls.authorized_client = Client()
        cls.authorized_client.force_login(cls.user)

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_cache_index_pages(self):
        """Тестируем кэш главной страницы."""
        new_post = Post.objects.create(
            author=CacheViewsTest.user,
            text='Новый тестовый пост',
        )
        response_1 = self.authorized_client.get(
            reverse('posts:index')
        )
        response_content_1 = response_1.content
        new_post.delete()
        response_2 = self.authorized_client.get(
            reverse('posts:index')
        )
        response_content_2 = response_2.content
        self.assertEqual(response_content_1, response_content_2)
        cache.clear()
        response_3 = self.authorized_client.get(
            reverse('posts:index')
        )
        response_content_3 = response_3.content
        self.assertNotEqual(response_content_2, response_content_3)


class FollowViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.author = User.objects.create_user(username='someauthor')

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

    def test_user_follower_authors(self):
        '''Посты доступны пользователю, который подписался на автора.
           Увеличение подписок автора'''
        follow_count = Follow.objects.count()
        new_author = User.objects.create(username='New author')
        self.authorized_client_1.get(
            reverse(
                'posts:profile_follow',
                kwargs={'username': new_author.username}
            )
        )
        follow = Follow.objects.last()
        self.assertEqual(Follow.objects.count(), follow_count + 1)
        self.assertEqual(follow.author, new_author)
        self.assertEqual(follow.user, self.user_1)

    def test_user_unfollower_authors(self):
        '''Посты не доступны пользователю, который не подписался на автора.
           Не происходит увеличение подписок автора'''
        follow_count = Follow.objects.count()
        new_author = User.objects.create(username='Very new author')
        authorized_client = Client()
        authorized_client.force_login(new_author)
        authorized_client.get(
            reverse(
                'posts:profile_follow',
                kwargs={'username': self.user.username}
            )
        )
        self.assertEqual(Follow.objects.count(), follow_count + 1)
        authorized_client.get(
            reverse(
                'posts:profile_unfollow',
                kwargs={'username': self.user.username}
            )
        )
        self.assertEqual(Follow.objects.count(), follow_count)

    def test_follower_see_new_post(self):
        '''У подписчика появляется новый пост избранного автора.'''
        post = Post.objects.create(
            author=self.user_1,
            text='Какой-то текст')
        Follow.objects.create(
            user=self.user_2,
            author=self.user_1)
        response = self.authorized_client_2.get(
            reverse('posts:follow_index'))
        self.assertIn(post, response.context['page_obj'].object_list)

    def test_unfollower_no_see_new_post(self):
        '''У неподписчика поста нет'''
        post = Post.objects.create(
            author=self.user_1,
            text='Какой-то текст')
        new_user = User.objects.create(username='Very new author')
        authorized_client = Client()
        authorized_client.force_login(new_user)
        Follow.objects.create(
            user=new_user,
            author=self.user_1)
        response = authorized_client.get(
            reverse('posts:follow_index'))
        self.assertIn(post, response.context['page_obj'].object_list)
        response = authorized_client.get(
            reverse(
                'posts:profile_unfollow',
                kwargs={'username': self.user_1.username}
            )
        )
        self.assertNotIn(Follow.objects.all(),
                         Follow.objects.filter(user=new_user,
                                               author=self.user_1))
