var RFH = (function (module) {
    module.BumperDisplay = function (options) {
        'use strict';
        var self = this;
        var tfClient = options.tfClient;
        var head = options.head;
        var camera = options.camera;
        var skins = options.skins;
        var visible = true;
        var $displayDiv = $('#bumper-contact-display');
        var $contactMarkers = $('.bumper');
        var $edgeMarkers = $('.edge-contact');
        var contacts = [];
        var contactEdgesActive = {'n': false, 'ne': false, 'e': false, 'se': false,
                                  's': false, 'sw': false, 'w': false, 'nw': false};

        var updateContacts = function () {
            contacts = []; 
            for (var i=0; i < contactDetectors.length; i+=1) {
                Array.prototype.push.apply(contacts, contactDetectors[i].getContacts());
            }
            updateDisplay();
        };

        var contactDetectors = [];
        for (var i=0; i<skins.length; i+=1) {
            contactDetectors.push(new module.SkinContactDetector({skinUtil: skins[i], 
                                                                  tfClient: tfClient}));
            contactDetectors[i].updateCBList.push(updateContacts);
        }

        self.show = function () {
            visible = true;
            $displayDiv.show();
        };

        self.hide = function () {
            visible = false;
            $displayDiv.hide();
        };

        var displayInViewContact = function (imgPt, marker) {
            // Show indicator of in-view contact at imgPt
            var w = $displayDiv.width(); 
            var h = $displayDiv.height(); 
            var left = imgPt[0]*w - 0.5*marker.width();
            var top = imgPt[1]*h - 0.5*marker.height();
            marker.css({left:left, top:top});
        };

        var inView = function (pt) {
            return (pt[0] >= 0 && pt[0] <=1 && pt[1] >= 0 && pt[1] <= 1);
        };

        var notInView = function (pt) {
            return !inView(pt);
        };

        var updateContactEdges = function (pts) {
            contactEdgesActive.n = false;
            contactEdgesActive.ne = false;
            contactEdgesActive.e = false;
            contactEdgesActive.se = false;
            contactEdgesActive.s = false;
            contactEdgesActive.sw = false;
            contactEdgesActive.w = false;
            contactEdgesActive.nw = false;
            var ang;
            var pt;
            for (var i=0; i<pts.length; i+=1) {
                pt = pts[i];
                ang = Math.atan2(-(pt[0]-0.5), -(pt[1]-0.5));
                console.log(pt[0], pt[1]," --> Ang: ", ang);
                if (ang > -Math.PI/6 && ang <= Math.PI/6) {
                    contactEdgesActive.n = true;
                } else if (ang > Math.PI/6 && ang <= Math.PI/3) {
                    contactEdgesActive.nw = true;
                } else if (ang > Math.PI/3 && ang <= 2*Math.PI/3) {
                    contactEdgesActive.w = true;
                } else if (ang > 2*Math.PI/3 && ang <= 5*Math.PI/6) {
                    contactEdgesActive.sw = true;
                } else if (ang > -Math.PI/3 && ang <= -Math.PI/6) {
                    contactEdgesActive.ne = true;
                } else if (ang > -2*Math.PI/3 && ang <= -Math.PI/3) {
                    contactEdgesActive.e = true;
                } else if (ang > -5*Math.PI/6 && ang <= -2*Math.PI/3) {
                    contactEdgesActive.se = true;
                } else if (ang < -5*Math.PI/6 || ang > 5*Math.PI/6) {
                    contactEdgesActive.s = true;
                }
            }
        };

        var displayEdgeContacts = function () {
            for (var dir in contactEdgesActive) {
                if (contactEdgesActive.hasOwnProperty(dir)) {
                    if (contactEdgesActive[dir]) {
                        $edgeMarkers.filter('.'+dir).show();
                    } else {
                        $edgeMarkers.filter('.'+dir).hide();
                    }
                }
            }
        };

        var updateDisplay = function () {
            if (!contacts.length || !visible) {
                $contactMarkers.hide();
                $edgeMarkers.hide();
                return;
             }
            var imgPts = camera.projectPoints(contacts, 'base_link');    
            if (imgPts === undefined) { return; }
            // Find and display contact points in the camera view
            var ptsInView = imgPts.filter(inView);
            var marker;
            for (var i=0; i<ptsInView.length && i<$contactMarkers.length; i+=1) {
                if (i<ptsInView.length) {
                    marker = $($contactMarkers[i]).show();
                    displayInViewContact(ptsInView[i], marker);
                } else {
                    $contactMarkers[i].hide();
                }
            }
            // Find and display out-of-view contacts along the edges
            var outOfView = imgPts.filter(notInView);
            updateContactEdges(outOfView); 
            displayEdgeContacts();
        };

        var lookOutOfView = function (event) {
            RFH.actionMenu.startAction('lookingAction');
            var dPan = 0;
            var dTilt = 0;
            var curTar = $(event.currentTarget);
            if (curTar.hasClass('n')) {
                    dTilt = -0.3;
            } else if (curTar.hasClass('ne')) {
                    dPan = -0.3;
                    dTilt = -0.3;
            } else if (curTar.hasClass('e')) {
                    dPan = -0.3;
            } else if (curTar.hasClass('se')) {
                    dPan = -0.3;
                    dTilt = 0.3;
            } else if (curTar.hasClass('s')) {
                    dTilt = 0.3;
            } else if (curTar.hasClass('sw')) {
                    dPan = 0.3;
                    dTilt = 0.3;
            } else if (curTar.hasClass('w')) {
                    dPan = 0.3;
            } else if (curTar.hasClass('nw')) {
                    dPan = 0.3;
                    dTilt = -0.3;
            } 
            head.delPosition(dPan, dTilt);
        };

        $edgeMarkers.on('click.rfh', lookOutOfView);
    };
        };
    return module;
})(RFH || {});
