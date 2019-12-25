# Parameter format '-{Parameter name}={Value as str or list}
def parse_args(strin: str) -> dict:
    dictout = {}
    while strin.find('-') != -1:  # while more parameters exist
        loc = strin.find('-')  # Save parameter symbol location.
        tmpstr = strin[loc + 1:]  # Save string, but lose the symbol.
        if tmpstr.find('-') >= 0:  # If another parameter symbol is found
            tmpstr = tmpstr[:tmpstr.find('-')]  # Cut it from this string.

        # Save key for dict, strip spaces, make case insensitive.
        key = tmpstr[:tmpstr.find('=')].rstrip().lstrip().lower()

        if tmpstr[tmpstr.find('=') + 1:].find(',') >= 0:  # Check if we found a comma in the value, denotes as list
            val = tmpstr[tmpstr.find('=') + 1:].split(',')  # Split the str into a list object
            for i in range(len(val)):  # Strip leading spaces from each value of list.
                val[i] = val[i].lstrip().rstrip()
        else:  # Else save as str object
            val = tmpstr[tmpstr.find('=') + 1:]
            val = val.lstrip().rstrip()

        dictout.update({key: val})  # Save key: val pair
        strin = strin[len(tmpstr):]  # Remove the param we've saved to the dict.
        # while
    return dictout  # Finally, hand the dict back.
