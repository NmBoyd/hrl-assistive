#!/usr/bin/env python

import numpy as np
import cv2
import video
from sklearn.cluster import KMeans
import time, random

help_message = '''
USAGE: opt_flow.py [<video_source>]

Keys:
 1 - toggle HSV flow visualization
 2 - toggle glitch

'''
last_center = None
color_list = [[0,0,255],
              [255,0,0],
              [0,255,0],
              [255,255,255]]
for i in xrange(10):
    color_list.append([random.randint(0,255),
                       random.randint(0,255),
                       random.randint(0,255) ])


def draw_flow(img, flow, step=16):
    h, w = img.shape[:2]
    y, x = np.mgrid[step/2:h:step, step/2:w:step].reshape(2,-1)
    fx, fy = flow[y,x].T
    lines = np.vstack([x, y, x+fx, y+fy]).T.reshape(-1, 2, 2)
    lines = np.int32(lines + 0.5)
    vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cv2.polylines(vis, lines, 0, (0, 255, 0))
    for (x1, y1), (x2, y2) in lines:
        cv2.circle(vis, (x1, y1), 1, (0, 255, 0), -1)
    return vis

def draw_clustered_flow(img, flow):
    global last_center, color_list
    
    h, w = flow.shape[:2]

    ## start = time.clock()
    yy, xx = np.meshgrid(range(w), range(h))
    flow_array = flow.reshape((h*w,2))
    mag_array  = np.linalg.norm(flow_array, axis=1)

    data = np.vstack([xx.ravel(), yy.ravel(), mag_array]).T
    flow_filt = data[data[:,2]>3.0]
    ## end = time.clock()
    ## print "%.2gs" % (end-start)

    n_clusters = 10
    if len(flow_filt) < n_clusters: return img

    if last_center is not None:
        clt = KMeans(n_clusters = n_clusters, init=last_center)
    else:
        clt = KMeans(n_clusters = n_clusters)
    clt.fit(flow_filt)
    last_center = clt.cluster_centers_

    cluster_centers.append(clt.cluster_centers_)

    overlay = img.copy()
    for ii, center in enumerate(clt.cluster_centers_):
        x = int(center[1])
        y = int(center[0])
        c = color_list[ii]
        cv2.circle(overlay, (x, y), 8, (c[0], c[1], int(c[2]*center[2])), -1)

    opacity = 0.4
    cv2.addWeighted(overlay, opacity, img, 1 - opacity, 0, img)
        
    return img

def draw_hsv(flow):
    h, w = flow.shape[:2]
    fx, fy = flow[:,:,0], flow[:,:,1]
    ang = np.arctan2(fy, fx) + np.pi
    v = np.sqrt(fx*fx+fy*fy)
    hsv = np.zeros((h, w, 3), np.uint8)
    hsv[...,0] = ang*(180/np.pi/2)
    hsv[...,1] = 255
    hsv[...,2] = np.minimum(v*4, 255)
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return bgr

def warp_flow(img, flow):
    h, w = flow.shape[:2]
    flow = -flow
    flow[:,:,0] += np.arange(w)
    flow[:,:,1] += np.arange(h)[:,np.newaxis]
    res = cv2.remap(img, flow, None, cv2.INTER_LINEAR)
    return res

if __name__ == '__main__':
    import sys
    print help_message
    try: fn = sys.argv[1]
    except: fn = 0

    scale = 0.3
    cam = video.create_capture(fn)
    ret, prev = cam.read()
    prev = cv2.resize(prev, (0,0), fx=scale, fy=scale) 
    
    prevgray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    show_hsv = False
    show_glitch = False
    cur_glitch = prev.copy()

    while True:
        ret, img = cam.read()
        img = cv2.resize(img, (0,0), fx=scale, fy=scale) 
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(prevgray, gray, 0.5, 3, 15, 3, 5, 1.2, 0)
        prevgray = gray
        
        cluster_img = draw_clustered_flow(img, flow)
        cv2.imshow('flow cluster', cluster_img)
        
        ## cv2.imshow('flow', draw_flow(gray, flow))
        if show_hsv:
            cv2.imshow('flow HSV', draw_hsv(flow))
        if show_glitch:
            cur_glitch = warp_flow(cur_glitch, flow)
            cv2.imshow('glitch', cur_glitch)

        ch = 0xFF & cv2.waitKey(1)
        if ch == 27:
            break
        if ch == ord('1'):
            show_hsv = not show_hsv
            print 'HSV flow visualization is', ['off', 'on'][show_hsv]
        if ch == ord('2'):
            show_glitch = not show_glitch
            if show_glitch:
                cur_glitch = img.copy()
            print 'glitch is', ['off', 'on'][show_glitch]

            
    cv2.destroyAllWindows()
