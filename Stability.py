#!/usr/bin/env python
# -*- coding: utf-8 -*-

# sys imports

# python imports
from glob import glob

# numpy imports
import numpy as np

# astropy imports
from astropy.io import fits
from astropy.modeling import fitting, models

# scipy imports
from scipy.signal import savgol_filter
from scipy.signal import find_peaks_cwt

# matplotlib imports
import matplotlib.pylab as plt


def classify_files():
    files = {}
    thar = []
    bias = []
    flat = []

    ffile = glob('*.fits')
    for f in ffile:
        with fits.open(f) as fh:
            h = fh[0].header['PROPID']
            if 'STABLE' in h:
                thar.append(f)
            if 'CAL_FLAT' in h:
                flat.append(f)
            if 'BIAS' in h:
                bias.append(f)
    files.update({'ThAr': thar, 'Bias': bias, 'Flat': flat})
    return files


def find_peaks(arc):
    goodpeaks = []
    # print('dimensions : {dim}, parameters :{param}'.format(dim=arc.shape, param=parameters))
    cutfiltered = savgol_filter(arc, 11, 3)
    peaks = find_peaks_cwt(cutfiltered, widths=np.arange(1, 20))
    for i in range(peaks.shape[0]-1, 0, -1):
        if cutfiltered[peaks[i]] < parameters[parameters['chip']]['Level'] or (peaks[i]-peaks)[i-1] > parameters[parameters['chip']]['Distance']:  # We find doublets of peaks, in order to fit both sky and object at the same time
            # print('Wrong !{0}, {1}, {2}'.format(i, peaks[i], peaks[i-1]))
            continue
        # print(i, peaks[i], cutfiltered[peaks[i]])
        goodpeaks.append(i)
    return peaks[goodpeaks]


def fit_orders_pair(arcdata):
    # plt.clf()
    cut = arcdata[:, parameters['center']]
    orderpositions = {}
    order = {}
    # print('peaks : {goodpeaks}'.format(goodpeaks=goodpeaks))
    # plt.plot(cutfiltered)
    # plt.scatter(peaks[goodpeaks], cutfiltered[peaks[goodpeaks]], c='green')
    goodpeaks = find_peaks(cut)
    print(goodpeaks)
    for i in range(2, len(goodpeaks)-1):
    # for i in range(1, 28):
        print('Detecting order number {order}. Peak : {pixel}counts  at pixel {peak}'.format(order=i, peak=goodpeaks[i], pixel=cut[goodpeaks[i]]))
        xg = np.arange(goodpeaks[i]-50, goodpeaks[i]+20)
        # print(xg)
        # plt.plot(xg, cutfiltered[peaks[goodpeaks][i]-50:peaks[goodpeaks][i]+20])
        g1 = models.Gaussian1D(amplitude=1., mean=goodpeaks[i], stddev=5)
        g2 = models.Gaussian1D(amplitude=1., mean=goodpeaks[i]-30, stddev=5)
        gg_init = g1 + g2
        fitter = fitting.SLSQPLSQFitter()
    # Pour fitter les deux gaussiennes, il faut normaliser les flux à 1
        gg_fit = fitter(gg_init, xg, cut[xg]/cut[xg].max(), verblevel=0)

        # gg_fit = fitter(gg_init, xg, cutfiltered[xg]/cutfiltered[goodpeaks[i]], verblevel=0)
        # print('Center of the order {order} : {science} and {sky}'.format(order=i, science=gg_fit.mean_0, sky=gg_fit.mean_1))
        sci = gg_fit.mean_0
        sky = gg_fit.mean_1
        skyorder = []
        scienceorder = []
        positions = []
        fit = []
        # print(sci, sky, amp)
# TODO : y n'a pas besoin d'être calculé à chaque fois, il ne change jamais
# pas la peine d'utiliser parameters[; center'] non plus, c'est une constante
        for index in range(100):
            try:
                y = parameters['center']+10*index
            except IndexError:
                print('Out of bounds')
                break
            xmobile = np.arange(sky.value-20, sci.value+20, dtype=np.int)
            ymobile = arcdata[xmobile, y]
            # print('center : {center}, index : {index}'.format(center=parameters['center'], index=index))
            # print('sci : {sci}, sky {sky}\nxmobile : {xmobile}, y: {y}, ymobile : {ymobile}'.format(xmobile=xmobile.shape,y=y, ymobile=ymobile, sci=sci.value, sky=sky.value))
            g1 = models.Gaussian1D(amplitude=1., mean=sci, stddev=5)
            g2 = models.Gaussian1D(amplitude=1., mean=sky, stddev=5)
            g = g1 + g2
            gfit = fitter(g, xmobile, ymobile/ymobile.max(), verblevel=0)
            if gfit.mean_0 > parameters['Y'] or gfit.mean_1 > parameters['Y']:
                print('Out of bounds')
                break
            sci = gfit.mean_0
            sky = gfit.mean_1
            # print('Center of fibres at position {p} : sky : {sky}, sci : {sci}.'.format(p=y, sci=sci.value, sky=sky.value))
            skyorder.append(sky.value)
            scienceorder.append(sci.value)
            positions.append(y)
            fit.append(gfit)
        order.update({str(i): fit})
        orderpositions.update({str(i): positions})

        # plt.plot(xg, cutfiltered[peaks[goodpeaks[i]]]*gg_fit(xg))

    return order, orderpositions


def assess_stability():
    arclist = classify_files()
    print(arclist)
    return arclist


def set_parameters(arcfile):
    print('extracting information from file {arcfile}'.format(arcfile=arcfile))
    ff = fits.open(arcfile)
    parameters = {
            'HBDET': {
                'Level': 50,
                'Distance': 30,
                'NOrder': 27
                    },
            'HRDET': {
                'Level': 50,
                'Distance': 40,
                'NOrder': 33
                    },
            'X': ff[0].header['NAXIS1'],
            'Y': ff[0].header['NAXIS2'],
            'center': int(ff[0].header['NAXIS1']/2),
            'chip': ff[0].header['DETNAM'],
            'data': ff[0].data
                }
    return parameters


def prepare_data(data):
    if parameters['chip'] == 'HRDET':
        bias = fits.open('R201704150021.fits')
    else:
        bias = fits.open('H201704150021.fits')
    flat = fits.open(data)
    datasec = flat[0].header['DATASEC']
    print(datasec)
    x1, x2 = datasec[1:8].split(':')
    y1, y2 = datasec[9:15].split(':')
    # print(x1, x2, y1, y2)

    dt = flat[0].data[np.int(y1):np.int(y2), np.int(x1):np.int(x2)] - bias[0].data.mean()
# We crudely remove the cosmics by moving all pixels in the highest bin of a 50-bin histogram to the second lowest.
    hist, bins = np.histogram(dt, bins=50)
    dt[np.where(dt >= bins[-2])] = bins[2]

    return dt
def plot_orders(orderframe, orderpositions):
    pass


if __name__ == "__main__":
    arcfiles = assess_stability()
    parameters = set_parameters(arcfiles['Flat'][3])
    # tp = fits.open('H201704120017.fits')
    tp = 'H201704120017.fits'
    data = prepare_data(arcfiles['Flat'][3])
    # order, pos = fit_orders_pair(data)
