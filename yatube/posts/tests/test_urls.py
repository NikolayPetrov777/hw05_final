from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from ..models import Group, Post

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
        cls.INDEX = '/'
        cls.GROUP = f'/group/{cls.group.slug}/'
        cls.PROFILE = f'/profile/{cls.user.username}/'
        cls.POST_ID = f'/posts/{cls.post.id}/'
        cls.POST_ID_EDIT = f'/posts/{cls.post.id}/edit/'
        cls.CREATE = '/create/'
        cls.ADD_COMMENT = f'/posts/{cls.post.id}/comment/'
        cls.FOLLOW = '/follow/'
        cls.PROFILE_FOLLOW = f'/profile/{cls.user.username}/follow/'
        cls.PROFILE_UNFOLLOW = f'/profile/{cls.user.username}/unfollow/'
        cls.templates_url_names = {
            cls.INDEX: 'posts/index.html',
            cls.GROUP: 'posts/group_list.html',
            cls.PROFILE: 'posts/profile.html',
            cls.POST_ID: 'posts/post_detail.html',
            cls.POST_ID_EDIT: 'posts/create_post.html',
            cls.CREATE: 'posts/create_post.html',
            cls.FOLLOW: 'posts/follow.html',
        }

    def setUp(self):
        # Создаем неавторизованный клиент
        self.guest_client = Client()
        # Создаем второй клиент
        self.authorized_client = Client()
        # Авторизуем пользователя
        self.authorized_client.force_login(self.user)

    def test_urls_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        for address, template in self.templates_url_names.items():
            with self.subTest(address=address):
                response = self.authorized_client.get(address)
                self.assertTemplateUsed(response, template)

    def test_index_url_exists_at_desired_location(self):
        """Страница / доступна любому пользователю."""
        response = self.guest_client.get(self.INDEX)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_group_detail_url_exists_at_desired_location(self):
        """Страница /group/<slug>/ доступна любому пользователю."""
        response = self.guest_client.get(self.GROUP)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_profile_url_exists_at_desired_location(self):
        """Страница /profile/<username>/ доступна любому пользователю."""
        response = self.guest_client.get(self.PROFILE)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_post_id_url_exists_at_desired_location(self):
        """Страница /posts/<post_id>/ доступна любому пользователю."""
        response = self.guest_client.get(self.POST_ID)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_post_id_edit_url_exists_at_desired_location(self):
        """Страница /posts/<post_id>/edit/ доступна только автору."""
        self.user = User.objects.get(username=self.user)
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        response = self.authorized_client.get(self.POST_ID_EDIT)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_post_id_edit_redirect_anonymous_on_admin_login(self):
        """Страница по адресу /posts/<post_id>/edit/ перенаправит анонимного
        пользователя на страницу логина.
        """
        response = self.guest_client.get(self.POST_ID_EDIT, follow=True)
        self.assertRedirects(
            response, (f'/auth/login/?next={self.POST_ID_EDIT}'))

    def test_create_url_exists_at_desired_location(self):
        """Страница /create/ доступна только авторизованному пользователю."""
        response = self.authorized_client.get(self.CREATE)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_unexisting_page_url_exists_at_desired_location(self):
        """Страница /unexisting_page/ ведёт к ошибке."""
        response = self.authorized_client.get('/unexisting_page/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_add_comment_url_exists_at_desired_location(self):
        """Страница /posts/<int:post_id>/comment/
        доступна только авторизованному пользователю. Произойдёт
        редирект на страницу /posts/<post_id>/"""
        response = self.authorized_client.get(self.ADD_COMMENT)
        self.assertRedirects(response, (self.POST_ID))
        response = self.guest_client.get(self.ADD_COMMENT, follow=True)
        self.assertRedirects(
            response, (f'/auth/login/?next={self.ADD_COMMENT}'))

    def test_follow_url_exists_at_desired_location(self):
        """Страница /follow/ доступна только авторизованному пользователю."""
        response = self.authorized_client.get(self.FOLLOW)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response = self.guest_client.get(self.FOLLOW, follow=True)
        self.assertRedirects(
            response, (f'/auth/login/?next={self.FOLLOW}'))

    def test_profile_follow_url_exists_at_desired_location(self):
        """Страница /profile/<str:username>/follow/
        доступна только авторизованному пользователю. Произойдёт
        редирект на страницу /profile/<str:username>/"""
        response = self.authorized_client.get(self.PROFILE_FOLLOW)
        self.assertRedirects(response, (self.PROFILE))
        response = self.guest_client.get(self.PROFILE_FOLLOW, follow=True)
        self.assertRedirects(
            response, (f'/auth/login/?next={self.PROFILE_FOLLOW}'))

    def test_profile_unfollow_url_exists_at_desired_location(self):
        """Страница /profile/<str:username>/unfollow/
        доступна только авторизованному пользователю. Произойдёт
        редирект на страницу /profile/<str:username>/"""
        response = self.authorized_client.get(self.PROFILE_UNFOLLOW)
        self.assertRedirects(response, (self.PROFILE))
        response = self.guest_client.get(self.PROFILE_UNFOLLOW, follow=True)
        self.assertRedirects(
            response, (f'/auth/login/?next={self.PROFILE_UNFOLLOW}'))
