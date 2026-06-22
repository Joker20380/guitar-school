from django.shortcuts import render


def tuner_page(request):
    return render(request, "tuner.html")
