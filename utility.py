# Graduation Level
def graduation_level(cgpa):
    if cgpa >= 3.67:
        return "Distinction"
    elif cgpa >= 2.67:
        return "Merit"
    elif cgpa >= 2.0:
        return "Pass"
    else:
        return "Fail"