def data_converter(num):
    dat = str(num)
    length = len(dat)
    dat = ''

    if length <= 6:
        temp = int(num)
        temp = temp / 10**3
        dat = '{0:.2f}KB'.format(temp)
        return dat

    elif length <= 9:
        temp = int(num)
        temp = temp / 10**6
        dat = '{0:.2f}MB'.format(temp)
        return dat
    
    elif length <= 12:
        temp = int(num)
        temp = temp / 10**9
        dat = '{0:.2f}GB'.format(temp)
        return dat