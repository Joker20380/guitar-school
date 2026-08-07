from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("teachers/", views.teacher_list, name="teacher_list"),
    path("teachers/<slug:slug>/", views.teacher_detail, name="teacher_detail"),
    path("my/<slug:slug>/teachers/", views.my_course_teachers, name="my_course_teachers"),
    path("my/<slug:slug>/teachers/request/", views.request_teacher, name="request_teacher"),
    path("", views.course_list, name="list"),
    path("verify/<str:token>/", views.verify_course_request, name="verify"),
    path("activate/<str:token>/", views.activate_student_account, name="activate"),

    path("my/", views.my_courses, name="my_courses"),
    path("my/<slug:slug>/", views.student_course, name="student_course"),
    path("my/<slug:slug>/lesson/<int:lesson_id>/complete/", views.mark_lesson_complete, name="mark_lesson_complete"),

    path("<slug:slug>/apply/", views.course_apply, name="apply"),
    path("<slug:slug>/", views.course_detail, name="detail"),
]
