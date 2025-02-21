from numpy.core.fromnumeric import partition
from sklearn.neural_network import MLPRegressor
import pickle
import numpy
from netCDF4 import Dataset
import matplotlib.pyplot as plt
from math import sin, cos, sqrt, atan2, radians
import math, time, os
import utils
import sys
#import load_forcings

class MyModel(object):

    def __init__(self,site='',nfroot_orders=3):
        self.name = 'hybioml'
        self.site = site
        self.nsoil_layers  = 10
        self.nfroot_orders = nfroot_orders
        # site-specific input and generic ELM parameters
        elmsurfdat = Dataset('./surfdata/surfdata_'+site+'.nc','r')
        elmparms   = Dataset('./parameters/selm_default_parms.nc','r')
       
        #get active PFTs from surface data
        pct_nat_pft = elmsurfdat['PCT_NAT_PFT'][:].squeeze()
        pftind = numpy.nonzero(pct_nat_pft)[0]
        print('Number of active PFTS: '+str(len(pftind)))
        print('PFT index:',pftind)
        self.pftfrac = pct_nat_pft[pftind]
        self.npfts = len(pftind)
        
        # dictionary of parameters
        self.parms    = {}
        self.pdefault = {}
        self.pmin     = {}
        self.pmax     = {}
        #define the subset of elm parameters to be used in the model
        #...added fcur
        elm_parmlist = ['crit_dayl','ndays_on','ndays_off', \
                'flnr','slatop','leafcn','lflitcn','livewdcn','frootcn', \
                'deadwdcn','mbbopt','roota_par','rootb_par','fstor2tran', \
                'stem_leaf','croot_stem','flivewd','froot_leaf','grperc', \
                'br_mr','q10_mr','leaf_long','froot_long','season_decid', \
                'r_mort','lwtop_ann','q10_hr','k_l1','k_l2','k_l3','k_s1', \
                'k_s2','k_s3','k_s4','k_frag','rf_l1s1','rf_l2s2','rf_l3s3',\
                'rf_s1s2','rf_s2s3','rf_s3s4','cwd_flig','fr_flig','lf_flig', \
                'fr_flab','lf_flab','fr_fcel','br_xr','fcur']
        #get the elm parameters from the parameter file
        for p in elm_parmlist:
            if (len(elmparms[p][:]) > 1):
                self.parms[p] = numpy.ma.filled(elmparms[p][pftind])
            else:
                self.parms[p] = [numpy.ma.filled(elmparms[p][0])]
        #Additional selm parameters not in elm
        self.parms['gdd_crit'] = numpy.zeros([self.npfts])+400.
        self.parms['nue']      = numpy.zeros([self.npfts])+10.0
        self.parms['fpg']      = [0.8]
        self.parms['fpi']      = [0.8]
        self.parms['soil4ci']  = [1000.]
        self.parms['froot_phen_peak'] = numpy.zeros([self.npfts])+0.5
        self.parms['froot_phen_width']= numpy.zeros([self.npfts])+0.3
        #Parameters arising from TAM
        # TAM C/N
        self.parms['frootcn_t']  = numpy.zeros([self.npfts]) + 60#60.
        self.parms['frootcn_a']  = numpy.zeros([self.npfts]) + 42#42.
        self.parms['frootcn_m']  = numpy.zeros([self.npfts]) + 24#24.
        # TAM partitioning
        self.parms['frootpar_t'] = numpy.zeros([self.npfts]) + 0.5#0.5
        self.parms['frootpar_a'] = numpy.zeros([self.npfts]) + 0.3#0.3
        self.parms['frootpar_m'] = numpy.zeros([self.npfts]) + 0.2#0.2
        # TAM longevity
        self.parms['frootlong_t'] = numpy.zeros([self.npfts]) + 1.5#2.25
        self.parms['frootlong_a'] = numpy.zeros([self.npfts]) + 1.5#1.35
        self.parms['frootlong_m'] = numpy.zeros([self.npfts]) + 1.5#0.90
        # TAM chemistry
        self.parms['fr_flab_t'] = numpy.zeros([self.npfts]) + 0.25
        self.parms['fr_flab_a'] = numpy.zeros([self.npfts]) + 0.25
        self.parms['fr_flab_m'] = numpy.zeros([self.npfts]) + 0.25
        self.parms['fr_flig_t'] = numpy.zeros([self.npfts]) + 0.25
        self.parms['fr_flig_a'] = numpy.zeros([self.npfts]) + 0.25
        self.parms['fr_flig_m'] = numpy.zeros([self.npfts]) + 0.25
        self.parms['fr_fcel_t'] = numpy.zeros([self.npfts]) + 0.50
        self.parms['fr_fcel_a'] = numpy.zeros([self.npfts]) + 0.50
        self.parms['fr_fcel_m'] = numpy.zeros([self.npfts]) + 0.50
        # difference btw fine-root system GDD and leaf GDD
        self.parms['gdd_crit_gap']        = numpy.zeros([self.npfts]) + 0
        self.parms['mort_depth_efolding'] = numpy.zeros([self.npfts]) + 0.3743
        
        #set parameter ranges for UQ activities
        for p in self.parms:
            self.pdefault[p] = self.parms[p]
            if (p == 'crit_dayl'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+36000.
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+43000.
            elif (p == 'gdd_crit'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+150
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+750
            elif (p == 'gdd_crit_gap'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)-100
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+200
            elif (p == 'fpg'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+0.70
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+0.95
            elif (p == 'nue'):
              self.pmin[p] = numpy.multiply(self.parms[p][:], 0.5)
              self.pmax[p] = numpy.multiply(self.parms[p][:], 2.5)
            elif (p == 'mort_depth_efolding'):
              self.pmin[p] = numpy.multiply(self.parms[p][:], 0.5)
              self.pmax[p] = numpy.multiply(self.parms[p][:], 2.5)
            elif (p == 'frootlong_t'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+3.
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+10.
            elif (p == 'frootlong_a'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+0.5
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+4.
            elif (p == 'frootlong_m'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+0.13
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+1.
            elif (p == 'frootcn_t'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+20
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+184
            elif (p == 'frootcn_a'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+11
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+119
            elif (p == 'frootcn_m'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+7
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+25
            elif (p == 'frootpar_t'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+0.05
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+0.95
            elif (p == 'frootpar_a'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+0.05
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+0.95
            elif (p == 'frootpar_m'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+0.05
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+0.95
            elif (p == 'fcur'):
              self.pmin[p] = numpy.multiply(self.parms[p][:],0.0)+0.25
              self.pmax[p] = numpy.multiply(self.parms[p][:],0.0)+0.75
            elif (not 'season_decid' in p):
              self.pmin[p] = numpy.multiply(self.parms[p],0.50)
              self.pmax[p] = numpy.multiply(self.parms[p],1.50)
            #elif ():
            #self.nparms = self.nparms+len(self.parms[p])
        
        self.issynthetic = False
        self.ne = 1                      #number of ensemble members

        #Model outputs
        self.outvars = ['gpp_pft','npp_pft','gr_pft', 'mr_pft','hr','nee','lai_pft', \
                        'leafc_pft','leafc_stor_pft','frootc_pft','frootc_stor_pft', \
                        'livestemc_pft','deadstemc_pft','livecrootc_pft','deadcrootc_pft',\
                        'totecosysc','totsomc','totlitc','cstor_pft','sminn_vr', \
                        'nstor_pft','ndep','nfix','fpg_pft','fpi_vr','cwdc','totlitn', \
                        'ctcpools_vr','leafc_alloc_pft','frootc_alloc_pft','livestemc_alloc_pft', \
                        'deadstemc_alloc_pft','frootctam_pft','frootctam_pft_vr']

        #get neural network
        pkl_filename = './GPP_model_NN/bestmodel_daily.pkl'
        with open(pkl_filename, 'rb') as file:
          self.nnmodel = pickle.load(file)
        nsamples=20000
        self.nparms_nn = 14  #15
        ptrain_orig  = (numpy.loadtxt('./GPP_model_NN/ptrain_daily.dat'))[0:nsamples,:]
        self.pmin_nn = numpy.zeros([self.nparms_nn], numpy.float64)
        self.pmax_nn = numpy.zeros([self.nparms_nn], numpy.float64)
        for i in range(0,self.nparms_nn):
          self.pmin_nn[i] = min(ptrain_orig[:,i])
          self.pmax_nn[i] = max(ptrain_orig[:,i])

    def hybioml_instance(self, parms, use_nn=False, seasonal_rootalloc=False,spinup_cycles=0, pftwt=[1.0,0,0]):
        """
        Run the sELM model for a single set of parameters
        """
        calc_nlimitation = True
        npfts         = self.npfts
        nfroot_orders = self.nfroot_orders
        
        ######################################
        # New VARs arisng from root complexity
        #####################################
        #
        #froot_partition_0 = [1/nfroot_orders] * nfroot_orders
        #frootcn = numpy.zeros([npfts,nfroot_orders],numpy.float64)
        #fr_flab = numpy.zeros([npfts,nfroot_orders],numpy.float64)
        #fr_flig = numpy.zeros([npfts,nfroot_orders],numpy.float64)
        # evergreen fine root longevity
        #froot_long = numpy.zeros([npfts,nfroot_orders],numpy.float64)

        if nfroot_orders == 1:
           #froot_partition = [1/nfroot_orders] * nfroot_orders
           froot_partition = numpy.array([numpy.array([1]*npfts)]).T
           frootcn         = numpy.tile(parms['frootcn'],(nfroot_orders,1)).T
           fr_flab         = numpy.tile(parms['fr_flab'],(nfroot_orders,1)).T
           fr_flig         = numpy.tile(parms['fr_flig'],(nfroot_orders,1)).T
           fr_fcel         = numpy.tile(parms['fr_fcel'],(nfroot_orders,1)).T
           froot_long      = numpy.tile(parms['froot_long'],(nfroot_orders,1)).T
        elif nfroot_orders == 2:
           #froot_partition = [0.6, 0.4] 
           #frootcn[:,:] = numpy.tile([35,60],(npfts,1)) #24,60
           froot_partition = [0.2857, 1.-0.2857]
           frootcn = numpy.tile([24,60],(npfts,1))
           fr_flab = numpy.tile([0.25,0.25],(npfts,1))
           fr_flig = numpy.tile([0.25,0.25],(npfts,1))
           #froot_long[:,:] = numpy.tile([1.0,1.5],(1,1))
           froot_long = numpy.tile([i*2 for i in parms['froot_long']],(nfroot_orders,1)).T *\
             numpy.array([0.4,0.6]) #0.4, 0.6
        elif nfroot_orders == 3:
           #froot_partition = [0.5, 0.3, 0.2] 
           #frootcn[:,:] = numpy.tile([35,48.5,60],(npfts,1))
           #froot_partition = [0.2, 0.3, 0.5] # [T,A,M]
           froot_partition = numpy.array([parms['frootpar_t'],parms['frootpar_a'],parms['frootpar_m']]).T
           #frootcn[:,:] = numpy.tile([24,42,60],(npfts,1))
           frootcn = numpy.array([parms['frootcn_t'],parms['frootcn_a'],parms['frootcn_m']]).T
           #fr_flab[:,:] = numpy.tile([0.25,0.25,0.25],(npfts,1))
           #fr_flig[:,:] = numpy.tile([0.25,0.25,0.25],(npfts,1))
           fr_flab = numpy.array([parms['fr_flab_t'],parms['fr_flab_a'],parms['fr_flab_m']]).T
           fr_flig = numpy.array([parms['fr_flig_t'],parms['fr_flig_a'],parms['fr_flig_m']]).T
           fr_fcel = numpy.array([parms['fr_fcel_t'],parms['fr_fcel_a'],parms['fr_fcel_m']]).T

           #froot_long[:,:]   = numpy.tile([0.5,1.0,1.5],(1,1))
           #froot_long[:,:] = numpy.tile([i*3 for i in parms['froot_long']],(nfroot_orders,1)).T *\
           #  numpy.array([0.2,0.3,0.5]) #0.2,0.3,0.5
           #froot_lit_partition = numpy.array([1, 1, 1])
           froot_long = numpy.array([parms['frootlong_t'],parms['frootlong_a'],parms['frootlong_m']]).T

        
        #--------------- Initialize ------------------------
        #Flux variables
        gpp = self.output['gpp_pft']
        npp = self.output['npp_pft']
        gr  = self.output['gr_pft']
        mr  = self.output['mr_pft']
        hr  = self.output['hr']
        nee = self.output['nee']
        #State variables
        lai         = self.output['lai_pft']
        leafc       = self.output['leafc_pft']
        leafc_stor  = self.output['leafc_stor_pft']
        frootc      = self.output['frootc_pft']      # total root mass
        frootc_o    = self.output['frootctam_pft']   # order-based root mass
        frootc_ovr  = self.output['frootctam_pft_vr']# order- & layer-based root mass
        frootc_stor = self.output['frootc_stor_pft']
        livestemc   = self.output['livestemc_pft']
        deadstemc   = self.output['deadstemc_pft']
        livecrootc  = self.output['livecrootc_pft']
        deadcrootc  = self.output['deadcrootc_pft']
        totecosysc  = self.output['totecosysc']
        totsomc     = self.output['totsomc']
        totlitc     = self.output['totlitc']
        cstor       = self.output['cstor_pft']
        sminn_vr    = self.output['sminn_vr']
        nstor       = self.output['nstor_pft']
        ndep        = self.output['ndep']
        nfix        = self.output['nfix']
        fpg         = self.output['fpg_pft']
        fpi_vr      = self.output['fpi_vr']
        cwdc        = self.output['cwdc']
        totlitn     = self.output['totlitn']
        ctcpools_vr = self.output['ctcpools_vr']
        leafc_alloc     = self.output['leafc_alloc_pft']
        frootc_alloc    = self.output['frootc_alloc_pft']
        livestemc_alloc = self.output['livestemc_alloc_pft']
        deadstemc_alloc = self.output['deadstemc_alloc_pft']

        ##############################
        #vertically resolved variables (local)
        # ...root_frac can be made order-specific, BUT assumed to be the same
        # ...a depth correction coefficient for fine-root longevity added
        root_frac    = numpy.zeros([npfts,self.nsoil_layers], numpy.float64)
        surf_prof    = numpy.zeros([self.nsoil_layers], numpy.float64)
        depth_scalar = numpy.zeros([self.nsoil_layers], numpy.float64)+1.0
        long_scalar  = numpy.zeros([npfts,self.nsoil_layers], numpy.float64)+1.0
        #set soil layers
        decomp_depth_efolding = 0.3743
        if (self.nsoil_layers == 1):
          surf_prof[0]   = 1.0
          root_frac[:,0] = 1.0
        else:
          soil_nodes = numpy.zeros([self.nsoil_layers], numpy.float64)
          soil_dz    = numpy.zeros([self.nsoil_layers], numpy.float64)
          soil_hi    = numpy.zeros([self.nsoil_layers], numpy.float64)
          soil_depth = numpy.zeros([self.nsoil_layers], numpy.float64)
          
          for i in range(0,self.nsoil_layers):
            soil_nodes[i] = 0.025*(numpy.exp(0.5*(i+0.5))-1)
           
          for i in range(0,self.nsoil_layers):
            if (i == 0):
              soil_dz[i]    = 0.5*(soil_nodes[0]+soil_nodes[1])
              soil_hi[i]    = 0.5*(soil_nodes[i]+soil_nodes[i+1])
              soil_depth[i] = soil_dz[i]/2.0
            elif (i < self.nsoil_layers-1):
              soil_dz[i]    = 0.5*(soil_nodes[i+1]-soil_nodes[i-1])
              soil_hi[i]    = 0.5*(soil_nodes[i]  +soil_nodes[i+1])
              soil_depth[i] = soil_hi[i-1]+soil_dz[i]/2.0
            else: 
              soil_dz[i]    = 1.5058
              soil_hi[i]    = 3.8018   #layer 10 from CLM
              soil_depth[i] = soil_hi[i-1]+soil_dz[i]/2.0
            surf_prof[i]    = (numpy.exp(-10.0*soil_nodes[i])) / soil_dz[i]
            depth_scalar[i] = numpy.exp(-soil_depth[i] / decomp_depth_efolding)
            # longevity correction for depth
            long_scalar[:,i]  = 1. + numpy.exp(-soil_depth[i] / parms['mort_depth_efolding'])
          
          # coarse root profile
          for i in range(0,self.nsoil_layers):
            for p in range(0,npfts):
              if (i == 0):
                root_frac[p,i] = 0.5*(numpy.exp(-1.0*parms['roota_par'][p]*0.0)+ \
                                      numpy.exp(-1.0*parms['rootb_par'][p]*0.0)- \
                                      numpy.exp(-1.0*parms['roota_par'][p]*soil_hi[i]) - \
                                      numpy.exp(-1.0*parms['rootb_par'][p]*soil_hi[i]) )
              else:
                root_frac[p,i] = 0.5*(numpy.exp(-1.0*parms['roota_par'][p]*soil_hi[i-1]) + \
                                      numpy.exp(-1.0*parms['rootb_par'][p]*soil_hi[i-1]) - \
                                      numpy.exp(-1.0*parms['roota_par'][p]*soil_hi[i])   - \
                                      numpy.exp(-1.0*parms['rootb_par'][p]*soil_hi[i]))
        # normalization
        for p in range(0,npfts):
          root_frac[p,:] = root_frac[p,:]/sum(root_frac[p,:])
        surf_prof = surf_prof/sum(surf_prof)

        ########################################
        #Set nonzero initial States 
        for p in range(0,npfts):
          if parms['season_decid'][p] == 1:
            leafc_stor[p,0] = 10.0
          else:
            leafc[p,0]      = 10.0 
        nstor[:,0]          = 1.0
        ctcpools_vr[6,:,0]  = parms['soil4ci'][0]
        ctcpools_vr[14,:,0] = parms['soil4ci'][0]/10.0   #ASSUME CN of 10

        #Forcings
        tmax = self.forcings['tmax']
        tmin = self.forcings['tmin']
        rad  = self.forcings['rad']
        doy  = self.forcings['doy']
        cair = self.forcings['cair']
        dayl = self.forcings['dayl']
        btran= self.forcings['btran']
        #Coefficents for ACM (GPP submodel)
        a=numpy.zeros([npfts,10], numpy.float64)
        for p in range(0,npfts):
          a[p,:] = [parms['nue'][p], 0.0156935, 4.22273, 208.868, 0.0453194, 0.37836, 7.19298, 0.011136, 2.1001, 0.789798]

        #Turnover times for CTC model
        k_ctc = [parms['k_l1'][0],parms['k_l2'][0],parms['k_l3'][0],parms['k_s1'][0], \
                 parms['k_s2'][0],parms['k_s3'][0],parms['k_s4'][0],parms['k_frag'][0]]
        #Respiration fractions for CTC model pools
        rf_ctc = [parms['rf_l1s1'][0],parms['rf_l2s2'][0],parms['rf_l3s3'][0] , \
                  parms['rf_s1s2'][0],parms['rf_s2s3'][0],parms['rf_s3s4'][0], 1.0, 0.0]
        #transfer matrix for CTC model
        tr_ctc = numpy.zeros([8,8],numpy.float64)
        tr_ctc[0,3] = 1.0 - parms['rf_l1s1'][0]
        tr_ctc[1,4] = 1.0 - parms['rf_l2s2'][0]
        tr_ctc[2,5] = 1.0 - parms['rf_l3s3'][0]
        tr_ctc[3,4] = 1.0 - parms['rf_s1s2'][0]
        tr_ctc[4,5] = 1.0 - parms['rf_s2s3'][0]
        tr_ctc[5,6] = 1.0 - parms['rf_s3s4'][0]
        tr_ctc[7,1] = parms['cwd_flig'][0]
        tr_ctc[7,2] = 1.0 - parms['cwd_flig'][0]

        #Initialize local variables
        gdd                = numpy.zeros([npfts], numpy.float64)+0.0
        #gdd_froot=numpy.zeros([npfts], numpy.float64)+0.0
        leafon             = numpy.zeros([npfts], numpy.float64)+0.0
        leafoff            = numpy.zeros([npfts], numpy.float64)+0.0
        frooton            = numpy.zeros([npfts], numpy.float64)+0.0
        leafc_trans        = numpy.zeros([npfts], numpy.float64)+0.0
        frootc_trans       = numpy.zeros([npfts], numpy.float64)+0.0
        leafc_trans_tot    = numpy.zeros([npfts], numpy.float64)+0.0
        frootc_trans_tot   = numpy.zeros([npfts], numpy.float64)+0.0
        leafc_litter       = numpy.zeros([npfts], numpy.float64)+0.0
        # OLD
        #frootc_litter = numpy.zeros([npfts], numpy.float64)+0.0
        # NEW
        #frootc_litter = numpy.zeros([npfts,nfroot_orders], numpy.float64)+0.0
        frootc_litter_ovr  = numpy.zeros([npfts,nfroot_orders,self.nsoil_layers], numpy.float64)+0.0
        leafc_litter_tot   = numpy.zeros([npfts], numpy.float64)+0.0
        # OLD
        #frootc_litter_tot = numpy.zeros([npfts], numpy.float64)+0.0
        # NEW
        #frootc_litter_tot = numpy.zeros([npfts,nfroot_orders], numpy.float64)+0.0
        leafn_litter        = numpy.zeros([npfts], numpy.float64)+0.0
        livestemc_turnover  = numpy.zeros([npfts], numpy.float64)+0.0
        livecrootc_turnover = numpy.zeros([npfts], numpy.float64)+0.0
        annsum_npp          = numpy.zeros([npfts], numpy.float64)+0.0
        annsum_npp_temp     = numpy.zeros([npfts], numpy.float64)+0.0
        retransn            = numpy.zeros([npfts], numpy.float64)+0.0
        annsum_retransn     = numpy.zeros([npfts], numpy.float64)+0.0
        annsum_retransn_temp= numpy.zeros([npfts], numpy.float64)+0.0
        annsum_gpp          = numpy.zeros([npfts], numpy.float64)+1000.0
        annsum_gpp_temp     = numpy.zeros([npfts], numpy.float64)+1000.0
        availc              = numpy.zeros([npfts], numpy.float64)+0.0
        cstor_alloc         = numpy.zeros([npfts], numpy.float64)+0.0
        xsmr                = numpy.zeros([npfts], numpy.float64)+0.0
        callom              = numpy.zeros([npfts], numpy.float64)+0.0
        nallom              = numpy.zeros([npfts], numpy.float64)+0.0
        leafcstor_alloc     = numpy.zeros([npfts], numpy.float64)+0.0
        frootcstor_alloc    = numpy.zeros([npfts], numpy.float64)+0.0
        livecrootc_alloc    = numpy.zeros([npfts], numpy.float64)+0.0
        deadcrootc_alloc    = numpy.zeros([npfts], numpy.float64)+0.0
        plant_ndemand       = numpy.zeros([npfts], numpy.float64)+0.0
        plant_nalloc        = numpy.zeros([npfts], numpy.float64)+0.0
        cstor_turnover      = numpy.zeros([npfts], numpy.float64)+0.0
        #
        met_thistimestep_norm=numpy.zeros([1,self.nparms_nn], numpy.float64)
        
        #Run the model
        for s in range(0,spinup_cycles+1):
          #totecosysc_last = totecosysc[0]
          if (s > 0):
            for p in range(0,npfts):
              leafc_stor[p,0]  = leafc_stor[p,self.nobs-1]
              leafc[p,0]       = leafc[p,self.nobs-1]
              frootc_stor[p,0] = frootc_stor[p,self.nobs-1]
              frootc_ovr[p,:,:,0]= frootc_ovr[p,:,:,self.nobs-1]
              frootc_o[p,:,0]    = frootc_o[p,:,self.nobs-1]
              frootc[p,0]        = frootc[p,self.nobs-1]#sum(frootc_o[p,:,0])
              lai[p,0]         = lai[p,self.nobs-1]
              livestemc[p,0]   = livestemc[p,self.nobs-1]
              deadstemc[p,0]   = deadstemc[p,self.nobs-1]
              livecrootc[p,0]  = livecrootc[p,self.nobs-1]
              deadcrootc[p,0]  = deadcrootc[p,self.nobs-1]
              cstor[p,0]       = cstor[p,self.nobs-1]
              nstor[p,0]       = nstor[p,self.nobs-1]
              fpg[p,0]         = fpg[p,self.nobs-1]
            for nl in range(0,self.nsoil_layers):
              ctcpools_vr[:,nl,0]  = ctcpools_vr[:,nl,self.nobs-1]
              sminn_vr[nl,0]       = sminn_vr[nl,self.nobs-1]
            if (s == spinup_cycles and spinup_cycles > 0):
              #accelerated mortality and spinup
              for p in range(0,npfts):
                deadstemc[p,0] = deadstemc[p,0]*10   ## 10 -> 1
                deadcrootc[p,0] = deadcrootc[p,0]*10   ## 10 -> 1
              for nl in range(0,self.nsoil_layers):
                ctcpools_vr[5,nl,0]  = ctcpools_vr[5,nl,0] * 5.0
                ctcpools_vr[6,nl,0]  = ctcpools_vr[6,nl,0] * 30.0
                ctcpools_vr[7,nl,0]  = ctcpools_vr[7,nl,0] * 3.0
                ctcpools_vr[13,nl,0] = ctcpools_vr[13,nl,0]* 5.0
                ctcpools_vr[14,nl,0] = ctcpools_vr[14,nl,0]* 30.0
                ctcpools_vr[15,nl,0] = ctcpools_vr[15,nl,0]* 3.0


          for v in range(0,self.nobs):
            # 1st loop over PFTs
            sum_plant_ndemand = 0.0
            for p in range(0,npfts):
              
              ###########################
              # Dynamic or Fixed Root Profile of CTAM
              # ...PFT-specific fractions of each pool in each layer
              # ...Constrained by C-Root profile but modulated by environmental factors:
              # ......temp and water
              # ...1) It should be updated in each time step
              # .....
              #... 2) Fixed distrubition but depth-dependent death
              ############################
              #root_frac_o = numpy.tile (root_frac[p,:],(nfroot_orders,1))
              
              # --------------------1.  Phenology -------------------------
              #Decidous phenology: asynchronous leaf & fine-root phenology
              #...fine root production from translocation from storage remains synchronous
              #...But, fine root shedding decoupled from leaf unfolding and became the same as evergreen
              if (parms['season_decid'][p] == 1):
                gdd_last = gdd[p]
                gdd_base = 0.0
                gdd[p] = (doy[v] > 1) * (gdd[p] + max(0.5*(tmax[v]+tmin[v])-gdd_base, 0.0))
                #leaf on
                if (gdd[p] >= parms['gdd_crit'][p] and gdd_last < parms['gdd_crit'][p]):
                  leafon[p] = parms['ndays_on'][0]
                  leafc_trans_tot[p]  = leafc_stor[p,v] * parms['fstor2tran'][0]
                  #frootc_trans_tot[p] = frootc_stor[p,v]*parms['fstor2tran'][0]
                if (leafon[p] > 0):
                  leafc_trans[p]  = leafc_trans_tot[p]  / parms['ndays_on'][0]
                  #frootc_trans[p] = frootc_trans_tot[p] / parms['ndays_on'][0]
                  leafon[p] = leafon[p] - 1
                else:
                  leafc_trans[p]  = 0.0
                  #frootc_trans[p] = 0.0
                #fine-root on
                if (gdd[p] >= parms['gdd_crit'][p]+parms['gdd_crit_gap'][p] and gdd_last < parms['gdd_crit'][p]+parms['gdd_crit_gap'][p]):
                  frooton[p] = parms['ndays_on'][0]
                  frootc_trans_tot[p] = frootc_stor[p,v]*parms['fstor2tran'][0]
                if (frooton[p] > 0):
                  frootc_trans[p] = frootc_trans_tot[p] / parms['ndays_on'][0]
                  frooton[p] = frooton[p] - 1
                else:
                  frootc_trans[p] = 0.0
                #leaf off
                dayl_last = dayl[v-1]
                if (dayl_last >= parms['crit_dayl'][0]/3600. and dayl[v] < parms['crit_dayl'][0]/3600.):
                   leafoff[p] = parms['ndays_off'][0]
                   leafc_litter_tot[p] = leafc[p,v]
                if (leafoff[p] > 0):
                   leafc_litter[p]  = min(leafc_litter_tot[p]  / parms['ndays_off'][0], leafc[p,v])
                   leafoff[p] = leafoff[p] - 1
                else:
                   leafc_litter[p]  = 0.0
                leafn_litter[p] = leafc_litter[p] / parms['lflitcn'][p]
                retransn[p]     = leafc_litter[p] / parms['leafcn'][p] - leafn_litter[p]
                # fine root litter decoupled from leaf shedding
              #Evergreen phenology / leaf & fine-root mortality                            
              else:
                gdd_last = gdd[p]
                gdd_base = 0.0
                gdd[p] = (doy[v] > 1) * (gdd[p] + max(0.5*(tmax[v]+tmin[v])-gdd_base, 0.0))
                # storage to leaf on
                if (gdd[p] >= parms['gdd_crit'][p] and gdd_last < parms['gdd_crit'][p]):
                  leafon[p] = parms['ndays_on'][0]
                  leafc_trans_tot[p]  = leafc_stor[p,v] * parms['fstor2tran'][0]
                if (leafon[p] > 0):
                  leafc_trans[p]  = leafc_trans_tot[p] / parms['ndays_on'][0]
                  leafon[p] = leafon[p] - 1
                else:
                  leafc_trans[p]  = 0.0
                # storage to fine-roots on
                if (gdd[p] >= parms['gdd_crit'][p]+parms['gdd_crit_gap'][p] and gdd_last < parms['gdd_crit'][p]+parms['gdd_crit_gap'][p]):
                  frooton[p] = parms['ndays_on'][0]
                  frootc_trans_tot[p] = frootc_stor[p,v]*parms['fstor2tran'][0]
                if (frooton[p] > 0):
                  frootc_trans[p] = frootc_trans_tot[p] / parms['ndays_on'][0]
                  frooton[p] = frooton[p] - 1
                else:
                  frootc_trans[p] = 0.0
                # mortality            
                retransn[p]     = leafc[p,v]  * 1.0 / (parms['leaf_long'][p]*365. ) * (1.0 / parms['leafcn'][p] - 1.0 / parms['lflitcn'][p])
                leafc_litter[p] = parms['r_mort'][0] * leafc[p,v]/365.0  + leafc[p,v]  * 1.0 / (parms['leaf_long'][p]*365. )
                leafn_litter[p] = parms['r_mort'][0] * leafc[p,v]/365.0  / parms['leafcn'][p] +  \
                               leafc[p,v]  * 1.0 / (parms['leaf_long'][p]*365. ) / parms['lflitcn'][p]
                ##############
                # parms['r_mort'] & parms['froot_long'] both can be tailored to be order-specific
                ##############
                # OLD
                #frootc_litter[p]   = parms['r_mort'][0] * frootc[p,v]/365.0 + \
                #                     frootc[p,v] * 1.0 / (parms['froot_long'][p]*365.)
              
              #Calculate live wood turnover
              livestemc_turnover[p]  = parms['lwtop_ann'][0] / 365. * livestemc[p,v]
              livecrootc_turnover[p] = parms['lwtop_ann'][0] / 365. * livecrootc[p,v]
              retransn[p] = retransn[p] + (livestemc_turnover[p]+livecrootc_turnover[p]) * \
                                  (1.0/max(parms['livewdcn'][p],10.)-1.0/max(parms['deadwdcn'][p],10.))
              slatop = parms['slatop'][p]
              lai[p,v+1] = leafc[p,v] * slatop

              #---------------------2. GPP -------------------------------------
              #Calculate GPP flux using the ACM model (Williams et al., 1997)

              if (lai[p,v] > 1e-3):
                if (use_nn == False):
                  #Use the ACM model from DALEC
                  rtot = 1.0
                  psid = -2.0
                  myleafn = 1.0/(parms['leafcn'][p] * slatop)
                  gs = abs(psid)**a[p,9]/((a[p,5]*rtot+(tmax[v]-tmin[v])))
                  pp = max(lai[p,v],0.5)*myleafn/gs*a[p,0]*numpy.exp(a[p,7]*tmax[v])
                  qq = a[p,2]-a[p,3]
                  #internal co2 concentration
                  ci = 0.5*(cair[v]+qq-pp+((cair[v]+qq-pp)**2-4.*(cair[v]*qq-pp*a[p,2]))**0.5)
                  e0 = a[p,6]*max(lai[p,v],0.5)**2/(max(lai[p,v],0.5)**2+a[p,8])
                  cps   = e0*rad[v]*gs*(cair[v]-ci)/(e0*rad[v]+gs*(cair[v]-ci))
                  gpp[v+1] = cps*(a[p,1]*dayl[v]+a[p,4])
                  #ACM is not valid for LAI < 0.5, so reduce GPP linearly for low LAI
                  if (lai[p,v] < 0.5):
                    gpp[p,v+1] = gpp[p,v+1]*lai[p,v]/0.5
                  gpp[p,v+1] = gpp[p,v+1]*btran[v]
                else:
                   #Use the Neural network trained with ELM data
                   dayl_factor = (dayl[v]/max(dayl[0:365]))**2.0
                   flnr = parms['flnr'][p]
                   if (v < 10):
                     t10 = (tmax[v]+tmin[v])/2.0+273.15
                   else:
                     t10 = sum(tmax[v-10:v]+tmin[v-10:v])/20.0+273.15
                   #Use the NN trained on daily data
                   met_thistimestep=[btran[v], lai[p,v], lai[p,v]/4.0, tmax[v]+273.15, tmin[v]+273.15, t10, \
                                   rad[v]*1e6, 50.0, cair[v]/10.0, dayl_factor, flnr, slatop, parms['leafcn'][p], parms['mbbopt'][p]]
                   for i in range(0,self.nparms_nn):   #normalize
                     met_thistimestep_norm[0,i] = ( met_thistimestep[i] - self.pmin_nn[i] ) / (self.pmax_nn[i] - self.pmin_nn[i]) 
                   gpp[p,v+1] = max(self.nnmodel.predict(met_thistimestep_norm), 0.0)
              else:
                  gpp[p,v+1] = 0.0

              #--------------------3.  Maintenance respiration ------------------------
              #Maintenance respiration
              # ...change froot system mainteance respiration by order/pool
              trate = parms['q10_mr'][0]**((0.5*(tmax[v]+tmin[v])-25.0)/25.0)
              # OLD
              #mr[p,v+1] = (leafc[p,v]/parms['leafcn'][p] + frootc[p,v]/parms['frootcn'][p] + \
              #         (livecrootc[p,v]+livestemc[p,v])/max(parms['livewdcn'][p],10.))* \
              #         (parms['br_mr'][0]*24*3600)*trate
              # NEW
              mr[p,v+1] = (leafc[p,v]/parms['leafcn'][p] + sum(frootc_o[p,:,v]/frootcn[p,:]) + \
                          (livecrootc[p,v]+livestemc[p,v])/max(parms['livewdcn'][p],10.)) * \
                          (parms['br_mr'][0]*24*3600)*trate
              #Nutrient limitation
              availc[p] = max(gpp[p,v+1] - mr[p,v+1], 0.0)
              xsmr[p]   = max(mr[p,v+1]  - gpp[p,v+1],0.0)

              #---------------4.  Allocation and growth respiration -------------------
              # BWANG: CTAm Root Structure
              # frootc_alloc[p,v] treated as TOTAL potential allocation to fine roots,
              # which will be partitioned later among different pools (N) of fine roots.
              # 
              ##########################
              frg  = parms['grperc'][p]
              flw  = parms['flivewd'][p]
              f1   = parms['froot_leaf'][p]
              # Change the allocation to and partitioning of fine roots
              if (seasonal_rootalloc):
                  if (annsum_gpp_temp[p]/annsum_gpp[p] > parms['froot_phen_peak'][p]- \
                          parms['froot_phen_width'][p]/2.0 and annsum_gpp_temp[p]/annsum_gpp[p] \
                          < parms['froot_phen_peak'][p]+parms['froot_phen_width'][p]/2.0):
                    f1 = f1*1.0/(parms['froot_phen_width'][p])
                    #f1 = 1.0
                    # Partitioning of M-A-T changed
                    froot_partition = [0.5,0.3,0.2]
                  else:
                    f1 = f1
                    froot_partition = [0.2,0.3,0.5]
                  #Differentiate between transportive roots (T), absorptive (A), and Mycorhizal(M) 

              if (parms['stem_leaf'][p] < 0):
                f2   = max(-1.0*parms['stem_leaf'][p]/(1.0+numpy.exp(-0.004*(annsum_npp[p] - 300.0))) - 0.4, 0.1)
                f3   = parms['croot_stem'][p]
              else:
                f2 = parms['stem_leaf'][p]
                f3 = parms['croot_stem'][p]
              # callom and nallom
              callom[p] = (1.0+frg)*(1.0 + f1 + f2*(1+f3))
              # OLD
              #nallom[p] = 1.0 / parms['leafcn'][p] + f1 / parms['frootcn'][p] + \
              #      f2 * flw * (1.0 + f3) / max(parms['livewdcn'][p],10.) + \
              #      f2 * (1.0 - flw) * (1.0 + f3) / max(parms['deadwdcn'][p],10.)
              # NEW
              nallom[p] = 1.0 / parms['leafcn'][p] + f1 * sum(froot_partition[p,:]/frootcn[p,:]) + \
                    f2 * flw * (1.0 + f3) / max(parms['livewdcn'][p],10.) + \
                    f2 * (1.0 - flw) * (1.0 + f3) / max(parms['deadwdcn'][p],10.)
              
              # Actual allocation STARTs here
              # leafc_alloc[p,v]    = availc[p] * 1.0/callom[p] * parms['fcur'][p]
              # frootc_alloc[p,v]   = availc[p] * f1/callom[p]  * parms['fcur'][p]
              # leafcstor_alloc[p]  = availc[p] * 1.0/callom[p] * (1-parms['fcur'][p])
              # frootcstor_alloc[p] = availc[p] * f1/callom[p]  * (1-parms['fcur'][p])
              if (parms['season_decid'][p] == 1):
                leafc_alloc[p,v]    = availc[p] * 1.0/callom[p]*0.5
                frootc_alloc[p,v]   = availc[p] * f1/callom[p] *0.5
                leafcstor_alloc[p]  = availc[p] * 1.0/callom[p]*0.5
                frootcstor_alloc[p] = availc[p] * f1/callom[p] *0.5
              else:
                leafcstor_alloc[p]  = 0.
                frootcstor_alloc[p] = 0.
                leafc_alloc[p,v]    = availc[p] * 1.0/callom[p]
                frootc_alloc[p,v]   = availc[p] * f1 /callom[p]
              
              livestemc_alloc[p,v] = availc[p] * flw*f2/callom[p]
              deadstemc_alloc[p,v] = availc[p] * (1.0-flw) * f2/callom[p]
              livecrootc_alloc[p]  = availc[p] * flw*(f2*f3)/callom[p]
              deadcrootc_alloc[p]  = availc[p] * (1.0-flw) * f2*f3/callom[p]

              #Calculate nitrogen demand from smminn, subtracting off retranslocated proportion
              plant_ndemand[p]  = availc[p] * nallom[p]/callom[p] - annsum_retransn[p]*gpp[p,v+1]/annsum_gpp[p]
              sum_plant_ndemand = sum_plant_ndemand + pftwt[p] * plant_ndemand[p]

              if (calc_nlimitation):
                rc = 3.0 * max(annsum_npp[p] * nallom[p]/callom[p], 0.01)
                r = max(1.0, rc/max(nstor[p,v],1e-15))
                plant_nalloc[p] = (plant_ndemand[p] + annsum_retransn[p]*gpp[p,v+1]/annsum_gpp[p]) / r
                fpg[p,v] = 1/r    #Growth limiation due to npool resistance
                cstor_alloc[p] = availc[p] * (1.0 - fpg[p,v])
              else:
                fpg[p,v] = parms['fpg'][p]
                cstor_alloc[p] = availc[p] * (1.0 - parms['fpg'][p])
              
              # growth respiration:
              gr[p,v+1] = availc[p] * fpg[p,v] * frg * (1.0 + f1 + f2*(1+f3))/callom[p]
            #end of 1st loop over pfts

            #Calculate resistance term and actual uptake f_om npool
            ctc_cn = numpy.zeros([8,self.nsoil_layers], numpy.float64)+10.0   #default SOM pools to 10
            if (calc_nlimitation):
              #Calculate potential immobilization (assume from litter-> SOM transitions only)
              potential_immob_vr = numpy.zeros([self.nsoil_layers], numpy.float64)
              trate = parms['q10_hr']**((0.5*(tmax[v]+tmin[v])-10)/10.0)
              for p in range(0,3):
                for nl in range(0,self.nsoil_layers):
                  if (ctcpools_vr[p,nl,v] > 0 and ctcpools_vr[p+8,nl,v] > 0):
                    #Calculate CN ratios for litter pools (SOM pools are constant)
                    ctc_cn[p,nl] = ctcpools_vr[p,nl,v] / ctcpools_vr[p+8,nl,v]   
                  #Immobilization depends on transitions from litter (p) to SOM (p+3)
                  potential_immob_vr[nl] = potential_immob_vr[nl] + max((1.0-rf_ctc[p])*k_ctc[p]*trate * \
                     depth_scalar[nl]*ctcpools_vr[p,nl,v]*(1.0/ctc_cn[p+3,nl] - 1.0/ctc_cn[p,nl]), 0.0)
              #Calculate CWD CN ratio (pool 7) to be used later
              for nl in range(0,self.nsoil_layers):
                if (ctcpools_vr[7,nl,v] > 0 and ctcpools_vr[15,nl,v] > 0):
                  ctc_cn[7,nl] = ctcpools_vr[7,nl,v]/ctcpools_vr[15,nl,v]

              #############################
              #calculate fpi for each layer (microbial and plant competition)
              #...Vertically distribute N Demand following fine roots?
              plant_ndemand_vr = numpy.zeros([self.nsoil_layers])
              fpi = 0.0
              for nl in range(0,self.nsoil_layers):
                # if nfroot_orders == 3:
                #   #Method 1:Vertical distribution of plant N demand scales with root fractions
                #   #plant_ndemand_vr[nl] = plant_ndemand * root_frac[nl] # OLD
                #   if (sum(sminn_vr[:,v]) > 0):
                #     plant_ndemand_vr[nl] = sum(plant_ndemand * root_frac[:,nl] * pftwt)
                #     #plant_ndemand_vr[nl] = sum_plant_ndemand * root_frac[0,nl]
                #   else:
                #     if (s == 0):
                #       plant_ndemand_vr[nl] = sum_plant_ndemand
                #   #frootc_t[p,:,v]
                #if nfroot_orders == 1:
                
                #Method 2: Vertical distribution of plant N demand scales with available mineral N
                if (sum(sminn_vr[:,v]) > 0):
                  plant_ndemand_vr[nl] = sum_plant_ndemand * sminn_vr[nl,v] / sum(sminn_vr[:,v])
                else:
                  if (s == 0):
                    plant_ndemand_vr[nl] = sum_plant_ndemand

                # Compare with existing mineral N pool
                if (plant_ndemand_vr[nl] + potential_immob_vr[nl] >= sminn_vr[nl,v] and \
                   (plant_ndemand_vr[nl] + potential_immob_vr[nl]) > 0):
                  
                  fpi_vr[nl,v] = sminn_vr[nl,v] / (plant_ndemand_vr[nl] + potential_immob_vr[nl])               
                  
                  if (sum_plant_ndemand > 0):
                    fpi = fpi + fpi_vr[nl,v]*plant_ndemand_vr[nl]/sum_plant_ndemand
                  else:
                    fpi = 1.0
                else:
                  fpi_vr[nl,v] = 1.0
                  if (sum_plant_ndemand > 0):
                    fpi = fpi + 1.0*plant_ndemand_vr[nl]/sum_plant_ndemand
                  else:
                    fpi = 1.0
            #print v, fpi, plant_ndemand[0], nstor[0,v], retransn[p], plant_nalloc[p]
            #time.sleep(0.05)

            ###################################
            # new profile: distribution profile & litter input profile
            froot_dist = numpy.zeros([npfts,self.nsoil_layers],numpy.float64)
            for p in range(0,npfts):
              # if (sum(sminn_vr[:,v]) > 0):
              #   froot_dist[p,:] = root_frac[p] * sminn_vr[:,v]/sum(sminn_vr[:,v])
              # else:
              #   froot_dist[p,:] = root_frac[p]
              # froot_dist[p,:] = froot_dist[p,:]/sum(froot_dist[p,:])
              # keep the old profile
              froot_dist[p,:] = root_frac[p]
              # litter input
              if nfroot_orders == 1:
                frootc_litter_ovr[p,:,:]= frootc_ovr[p,:,:,v]*\
                                (parms['r_mort'][0]/365.0 + 1.0 / (froot_long[p,:]*365.0))[:,None]
              elif nfroot_orders == 3:
                #Coupled Death
                # ... when T root dies, A & M root must join; when A dies, M must join
                # ... scaled by exp(1/4)
                # matrix * matrix
                # frootc_litter_ovr[p,:,:] = frootc_ovr[p,:,:,v]*\
                #                 numpy.tile(long_scalar[p,:],(3,1))*\
                #                 (parms['r_mort'][0]/365.0 + 1.0 / (froot_long[p,:]*365.0))[:,None]
                frootc_litter_ovr[p,:,:]= frootc_ovr[p,:,:,v]*\
                                (parms['r_mort'][0]/365.0 + 1.0 / (froot_long[p,:]*365.0))[:,None]

                # #T root
                # frootc_litter_ovr[p,2,:] = (long_scalar*parms['r_mort'][0] * frootc_o[p,2,v]/365.0 + \
                #                             frootc_o[p,2,v] * 1.0 / (froot_long[p,2]*365.))*\
                #                             froot_lit_frac[p,2,:]
                # #A root
                # frootc_litter_ovr[p,1,:]=(long_scalar*parms['r_mort'][0] * frootc_o[p,1,v]/365.0 + \
                #                           frootc_o[p,1,v] * 1.0 / (froot_long[p,1]*365.))*\
                #                           froot_lit_frac[p,1,:]
                #                           #frootc_litter_ovr[p,2,:] * 1/numpy.exp(1/4)  
                # #M root
                # frootc_litter_ovr[p,0,:]=(long_scalar*parms['r_mort'][0] * frootc_o[p,0,v]/365.0 + \
                #                           frootc_o[p,0,v] * 1.0 / (froot_long[p,0]*365.))*\
                #                           froot_lit_frac[p,0,:]
                #                           #frootc_litter_ovr[p,1,:] * 1/numpy.exp(1/4)


            ###################################
            # Mortality fluxes
            # ... should be PFT- & Layer-specific
            # ... Distribute the fluxes across soil profile by by surf_prof 
            # ... frootc_litter_vr be order-specific based on a new profile
            # ... move the fine-root mortality from the phenology down below
            # .....as fine root litter decoupled from leaf shedding
            #...frootc_litter_ovr: pft-, order-, & depth-specific
            
            if (s < spinup_cycles):
              mort_factor = 10.0
            else:
              mort_factor = 1.0
            leafc_litter_vr      = numpy.zeros([npfts,self.nsoil_layers],numpy.float64)
            # OLD
            #frootc_litter_vr    = numpy.zeros([self.nsoil_layers],numpy.float64)
            # NEW
            frootc_litter_vr     = numpy.zeros([npfts,nfroot_orders,self.nsoil_layers],numpy.float64)
            leafn_litter_vr      = numpy.zeros([npfts,self.nsoil_layers],numpy.float64)
            livestemc_litter_vr  = numpy.zeros([npfts,self.nsoil_layers],numpy.float64)
            livecrootc_litter_vr = numpy.zeros([npfts,self.nsoil_layers],numpy.float64)
            deadstemc_litter_vr  = numpy.zeros([npfts,self.nsoil_layers],numpy.float64)
            deadcrootc_litter_vr = numpy.zeros([npfts,self.nsoil_layers],numpy.float64)
            cstor_litter_vr      = numpy.zeros([npfts,self.nsoil_layers],numpy.float64)
            nstor_litter_vr      = numpy.zeros([npfts,self.nsoil_layers],numpy.float64)
            for nl in range(0,self.nsoil_layers):
              for p in range(0,npfts):
                leafc_litter_vr[p,nl]  = pftwt[p] * leafc_litter[p]  * surf_prof[nl]
                # OLD
                #frootc_litter_vr[nl] = frootc_litter_vr[nl] + pftwt[p] * frootc_litter[p] * surf_prof[nl]
                # NEW 
                #frootc_litter_vr[:,nl] = frootc_litter_vr[:,nl] + pftwt[p] * frootc_litter[p,:] * surf_prof[nl]
                # weighted litter mass by PFT, order, and layer
                frootc_litter_vr[p,:,nl]   = pftwt[p] * frootc_litter_ovr[p,:,nl]
                leafn_litter_vr[p,nl]      = pftwt[p] * leafn_litter[p]  * surf_prof[nl]
                livestemc_litter_vr[p,nl]  = pftwt[p] * parms['r_mort'][0]/365.0 * livestemc[p,v] * surf_prof[nl]
                livecrootc_litter_vr[p,nl] = pftwt[p] * parms['r_mort'][0]/365.0 * livecrootc[p,v] * root_frac[p,nl]
                deadstemc_litter_vr[p,nl]  = pftwt[p] * parms['r_mort'][0] * mort_factor / 365.0 * deadstemc[p,v] * surf_prof[nl]
                deadcrootc_litter_vr[p,nl] = pftwt[p] * parms['r_mort'][0] * mort_factor / 365.0 * deadcrootc[p,v] * root_frac[p,nl]
                cstor_litter_vr[p,nl]      = pftwt[p] * parms['r_mort'][0]/365.0 * cstor[p,v] * surf_prof[nl]
                nstor_litter_vr[p,nl]      = pftwt[p] * parms['r_mort'][0]/365.0 * nstor[p,v] * surf_prof[nl]
            
            #########################################
            # Finally, update various plant structural pools accounting for new production
            # ....(w/ N limitation) and mortality
            #
            # Take XSMR from cpool instead (below)
            # Change frootc to be order-specific
            # frootc_alloc and frootc_trans NEED to be partitioned among T,A,&M, and distributed
            # 2nd loop over PFTs
            for p in range(0,npfts):
              cstor_turnover[p] = parms['br_xr'][p] * (3600.*24.) * cstor[p,v] * trate
              #increment plant C pools
              leafc[p,v+1]       = leafc[p,v]      + fpg[p,v]*leafc_alloc[p,v]   + leafc_trans[p] - leafc_litter[p]
              leafc_stor[p,v+1]  = leafc_stor[p,v] + fpg[p,v]*leafcstor_alloc[p] - leafc_trans[p]
              # OLD
              # frootc[p,v+1] = frootc[p,v] + fpg[p,v]*frootc_alloc[p,v] + frootc_trans[p] - frootc_litter[p]
              # pft-,order-, & layer-based mass
              for nl in range(0,self.nsoil_layers):
                frootc_ovr[p,:,nl,v+1] = numpy.maximum(
                  frootc_ovr[p,:,nl,v] + \
                  (frootc_alloc[p,v]*fpg[p,v] + frootc_trans[p])*froot_partition[p,:]*froot_dist[p,nl] -\
                  frootc_litter_ovr[p,:,nl],
                  [0]*nfroot_orders
                ) 
              # pft- & order-based (avoid negative values)
              frootc_o[p,:,v+1] = numpy.maximum(
                frootc_o[p,:,v] + \
                (frootc_alloc[p,v]*fpg[p,v] + frootc_trans[p])*froot_partition[p,:] - \
                numpy.sum(frootc_litter_ovr[p,:,:],axis=1),\
                [0]*nfroot_orders
              )
              #update frootc: pass frooc_t back to frootc (total fine root c)
              frootc[p,v+1] = numpy.sum(frootc_o[p,:,v+1])
              frootc_stor[p,v+1] = frootc_stor[p,v] + fpg[p,v]*frootcstor_alloc[p] - frootc_trans[p]  
              livestemc[p,v+1]   = livestemc[p,v]   + fpg[p,v]*livestemc_alloc[p,v] - parms['r_mort'][0] \
                      / 365.0 * livestemc[p,v] - livestemc_turnover[p]
              deadstemc[p,v+1]   = deadstemc[p,v]   + fpg[p,v]*deadstemc_alloc[p,v] - parms['r_mort'][0] \
                      * mort_factor / 365.0 * deadstemc[p,v] + livestemc_turnover[p]
              livecrootc[p,v+1]  = livecrootc[p,v]  + fpg[p,v]*livecrootc_alloc[p] - parms['r_mort'][0] \
                      / 365.0 * livecrootc[p,v] - livecrootc_turnover[p]
              deadcrootc[p,v+1]  = deadcrootc[p,v]  + fpg[p,v]*deadcrootc_alloc[p] - parms['r_mort'][0] \
                      * mort_factor / 365.0 * deadcrootc[p,v] + livecrootc_turnover[p]
              cstor[p,v+1]       = cstor[p,v] + cstor_alloc[p] - parms['r_mort'][0] / 365.0 * \
                      cstor[p,v] - cstor_turnover[p] - xsmr[p]
              #Increment plant N pools
              if (calc_nlimitation):
                nstor[p,v+1] = nstor[p,v] - parms['r_mort'][0] / 365.0 * nstor[p,v] + \
                        retransn[p] - plant_nalloc[p] + fpi*plant_ndemand[p]  
              
              #Calculate NPP
              npp[p,v+1] = gpp[p,v+1] - mr[p,v+1] - gr[p,v+1] - cstor_turnover[p]
              if (doy[v] == 1):
                annsum_npp[p] = annsum_npp_temp[p]
                annsum_npp_temp[p] = 0
                annsum_retransn[p] = annsum_retransn_temp[p]
                annsum_retransn_temp[p] = 0
                annsum_gpp[p] = annsum_gpp_temp[p]
                annsum_gpp_temp[p] = 0

              annsum_npp_temp[p]      = annsum_npp_temp[p]      + npp[p,v]
              annsum_retransn_temp[p] = annsum_retransn_temp[p] + retransn[p]
              annsum_gpp_temp[p]      = annsum_gpp_temp[p]      + gpp[p,v]
            # end of 2nd loop over PFTs

            # if v == 365*6:
            #     print("annsum_npp",annsum_npp)
            #     print("annsum_npp_temp",annsum_npp_temp)
            #     print("gr=",gr[:,v])
            #     print(doy[v])
            #     sys.exit()

            # ----------------- Litter and SOM decomposition model (CTC) --------------------
            # BWANG: Changes arising from CTAM structure
            # ... frootc_litter_vr being pft-, order-, & layer-specific
            # .....need to sum over PFTs and orders to derive layer-based total inputs
            ctc_input    = numpy.zeros([16,self.nsoil_layers],numpy.float64)  #inputs to pool
            ctc_output   = numpy.zeros([16,self.nsoil_layers],numpy.float64)  #Outputs from pool
            ctc_resp     = numpy.zeros([8, self.nsoil_layers],numpy.float64)  #Respiration from pool
            #Litter inputs to the system
            for nl in range(0,self.nsoil_layers):
              #Carbon
              ctc_input[0,nl] = sum(leafc_litter_vr[:,nl]*parms['lf_flab']) + sum(sum(frootc_litter_vr[:,:,nl] * fr_flab[:,:]))
              ctc_input[2,nl] = sum(leafc_litter_vr[:,nl]*parms['lf_flig']) + sum(sum(frootc_litter_vr[:,:,nl] * fr_flig[:,:]))
              ctc_input[1,nl] = sum(leafc_litter_vr[:,nl]*(1.0 - parms['lf_flab'] - parms['lf_flig'])) + \
                                sum(sum(frootc_litter_vr[:,:,nl]*fr_fcel[:,:]))
              ctc_input[7,nl] = sum(livestemc_litter_vr[:,nl] + livecrootc_litter_vr[:,nl] + deadcrootc_litter_vr[:,nl] + deadstemc_litter_vr[:,nl])
              #Nitrogen
              ctc_input[8,nl] = sum(leafn_litter_vr[:,nl]*parms['lf_flab']) + \
                                sum(sum(frootc_litter_vr[:,:,nl]*fr_flab[:,:] / frootcn[:,:]))
              ctc_input[10,nl] = sum(leafn_litter_vr[:,nl]*parms['lf_flig']) + \
                                sum(sum(frootc_litter_vr[:,:,nl]*fr_flig[:,:] / frootcn[:,:]))
              ctc_input[9,nl]= sum(leafn_litter_vr[:,nl]*(1.0 - parms['lf_flig'] - parms['lf_flab'])) +  \
                                sum(sum(frootc_litter_vr[:,:,nl]*fr_fcel[:,:] / frootcn[:,:]))
              ctc_input[15,nl] =sum((livestemc_litter_vr[:,nl] + livecrootc_litter_vr[:,nl]) / numpy.maximum(parms['livewdcn'],[10.]*npfts)) + \
                                sum((deadcrootc_litter_vr[:,nl] + deadstemc_litter_vr[:,nl]) / numpy.maximum(parms['deadwdcn'],[10.]*npfts))
            
            #########################
            ctc_to_sminn = numpy.zeros([self.nsoil_layers], numpy.float64)
            if (s < spinup_cycles):
              spinup_factors = [1.0, 1.0, 1.0, 1.0, 1.0, 5.0, 30.0, 3.0]
            else:
              spinup_factors = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
            for nl in range(0,self.nsoil_layers):
              trate = parms['q10_hr']**((0.5*(tmax[v]+tmin[v])-10)/10.0)
              for p1 in range(0,8):
                if (p1 < 3):
                   if (calc_nlimitation):
                     ctc_output[p1,nl]   = k_ctc[p1]*ctcpools_vr[p1,nl,v]*depth_scalar[nl]*trate*fpi_vr[nl,v] 
                     ctc_output[p1+8,nl] = k_ctc[p1]*ctcpools_vr[p1,nl,v]*depth_scalar[nl]*trate*fpi_vr[nl,v]/ctc_cn[p1,nl]
                   else:
                     ctc_output[p1,nl]   = k_ctc[p1]*ctcpools_vr[p1,nl,v]*depth_scalar[nl]*trate*parms['fpi']
                     ctc_output[p1+8,nl] = k_ctc[p1]*ctcpools_vr[p1,nl,v]*depth_scalar[nl]*trate*parms['fpi']/ctc_cn[p1,nl]
                else:
                   ctc_output[p1,nl]   = k_ctc[p1]*ctcpools_vr[p1,nl,v]*spinup_factors[p1]*depth_scalar[nl]*trate  #Decomposition (output)
                   ctc_output[p1+8,nl] = k_ctc[p1]*ctcpools_vr[p1,nl,v]*spinup_factors[p1]*depth_scalar[nl]*trate/ctc_cn[p1,nl]

                #Calculate HR and N mineralization from HR
                ctc_resp[p1,nl]   = ctc_output[p1,nl]*rf_ctc[p1]       
                if (ctcpools_vr[p1,nl,v] > 0):
                  ctc_to_sminn[nl] = ctc_to_sminn[nl] + ctc_resp[p1,nl] / ctc_cn[p1,nl] 
                for p2 in range(0,8):
                    #Transfer carbon from one pool to another
                    ctc_input[p2,nl] = ctc_input[p2,nl] + ctc_output[p1,nl]*tr_ctc[p1,p2]
                    if (p1 < 7):
                      ctc_input[p2+8,nl] = ctc_input[p2+8,nl] + ctc_output[p1,nl]*tr_ctc[p1,p2] / ctc_cn[p2,nl]
                      #Calculate nitrogen mineralized/immobilized
                      ctc_to_sminn[nl] = ctc_to_sminn[nl] + ctc_output[p1,nl]*tr_ctc[p1,p2] * \
                                        (1/ctc_cn[p1,nl] - 1/ctc_cn[p2,nl])
                    else:
                      #Fragmentation from CWD into litter - no immobilization/mineralization
                      ctc_input[p2+8,nl] = ctc_input[p2+8,nl] + ctc_output[p1,nl]*tr_ctc[p1,p2] / ctc_cn[p1,nl]
            

            #Calculate inputs and outputs from advection
            advection_rate = 0.000  #m/yr
            if (self.nsoil_layers > 1 and advection_rate > 0.0):
              for p in range(0,16):
                for nl in range(0,self.nsoil_layers):
                  if (nl < self.nsoil_layers-1):
                    ctc_output[p,nl] = ctc_output[p,nl] + ctcpools_vr[p,nl,v] * spinup_factors[p % 8] * \
                                       advection_rate / 365.0 / soil_depth[nl]
                  if (nl > 0):
                    ctc_input[p,nl] = ctc_input[p,nl] + ctcpools_vr[p,nl-1,v] * spinup_factors[p % 8] * \
                                       advection_rate / 365.0 / soil_depth[nl-1]
            
            hr[v+1]=0
            #Increment ctcpools
            for p in range(0,16):        #Handle both C and N
              for nl in range(0,self.nsoil_layers):
                ctcpools_vr[p,nl,v+1] = ctcpools_vr[p,nl,v] + ctc_input[p,nl] - ctc_output[p,nl]
                if (p < 8):
                  hr[v+1] = hr[v+1] + ctc_resp[p,nl]
 
            #Calculate NEE
            #nee[v+1]    = hr[v+1] - npp[v+1]
            #Total system carbon
            #totecosysc_tmp = 0.0
            totecosysc[v+1]= 0.0
            for p in range(0,npfts):
              totecosysc[v+1] = totecosysc[v+1] + pftwt[p] * (leafc[p,v+1]+leafc_stor[p,v+1]+sum(frootc_o[p,:,v+1])+ \
                                frootc_stor[p,v+1]+livestemc[p,v+1]+deadstemc[p,v+1]+livecrootc[p,v+1]+deadcrootc[p,v+1]+\
                                cstor[p,v+1])
            for nl in range(0,self.nsoil_layers):
              totecosysc[v+1] = totecosysc[v+1] + sum(ctcpools_vr[:,nl,v+1])
            
            totlitc[v+1] = sum(ctcpools_vr[0,:,v+1])+sum(ctcpools_vr[1,:,v+1])+sum(ctcpools_vr[2, :,v+1])
            totsomc[v+1] = sum(ctcpools_vr[3,:,v+1])+sum(ctcpools_vr[4,:,v+1])+sum(ctcpools_vr[5, :,v+1])+sum(ctcpools_vr[6, :,v+1])
            totlitn[v+1] = sum(ctcpools_vr[8,:,v+1])+sum(ctcpools_vr[9,:,v+1])+sum(ctcpools_vr[10,:,v+1])+sum(ctcpools_vr[11,:,v+1])
            cwdc[v+1]    = sum(ctcpools_vr[7,:,v+1])
            nee[v+1]     = totecosysc[v+1]-totecosysc[v]

            #Update soil mineral nitrogen
            ndep[v] = 0.115 / (365)
            nfix[v] = 0 # nitrogen fixation
            for p in range(0,self.npfts):
              nfix[v] = nfix[v] + pftwt[p] * (1.8 * (1.0 - numpy.exp(-0.003 * annsum_npp[p]))) / (365)            
            bdnr =0.05
            if (calc_nlimitation):
              for nl in range(0,self.nsoil_layers):
                # nfix_nl: total nfix of all PFTs by layer added
                nfix_nl = 0
                for p in range(0,self.npfts):
                  nfix_nl = nfix_nl + root_frac[p,nl] * pftwt[p] * (1.8 * (1.0 - numpy.exp(-0.003 * annsum_npp[p]))) / (365)
                sminn_vr[nl,v+1] = max(
                  sminn_vr[nl,v]*(1-bdnr) + nfix_nl + ndep[v]*surf_prof[nl] - fpi_vr[nl,v]*plant_ndemand_vr[nl] + ctc_to_sminn[nl],
                  0.0
                )
                #Old
                #sminn_vr[nl,v+1] = max(sminn_vr[nl,v]*(1-bdnr) + nfix[v]*root_frac[0,nl] + ndep[v]*surf_prof[nl] - \
                #                     fpi_vr[nl,v]*plant_ndemand_vr[nl] + ctc_to_sminn[nl], 0.0)
            
    def run_hybioml(self, spinup_cycles=0, lat_bounds=[-999,-999], lon_bounds=[-999,-999], \
                     do_monthly_output=False, do_output_forcings=False, pft=-1,          \
                     prefix='model', seasonal_rootalloc=False, use_nn=False, ensemble=False, \
                     myoutvars=[], use_MPI=False):
        """ 
        Run the hybioml model for a given site or region
        
        """
        ens_torun  = []
        indx_torun = []
        indy_torun = []
        pftwt_torun= numpy.zeros([self.npfts, 10000000], numpy.float64)
        n_active   = 0

        if (self.site == 'none'):
         if (use_MPI):
           from mpi4py import MPI
           comm=MPI.COMM_WORLD
           rank=comm.Get_rank()
           size=comm.Get_size()
           print(size, 'i am', rank)
         else:
           rank = 0
           size = 0
         if (rank == 0):
          mydomain = Dataset(oscm_dir+"/models/pftdata/domain.360x720_ORCHIDEE0to360.100409.nc4",'r')
          landmask = mydomain.variables['mask']
          myinput = Dataset(oscm_dir+"/models/pftdata/surfdata_360x720_DALEC.nc4")
          pct_pft    = myinput.variables['PCT_NAT_PFT']
          pct_natveg = myinput.variables['PCT_NATVEG']
          self.hdlatgrid = myinput.variables['LATIXY']
          self.hdlongrid = myinput.variables['LONGXY']
          self.x1 = int(round((lon_bounds[0]-0.25)*2))
          if (self.x1 < 0):
             self.x1 = self.x1+720
          self.x2 = int(round((lon_bounds[1]-0.25)*2))
          if (self.x2 < 0):
             self.x2 = self.x2+720
          self.nx = self.x2-self.x1+1
          self.y1 = int(round((lat_bounds[0]+89.75)*2))
          self.y2 = int(round((lat_bounds[1]+89.75)*2))
          self.ny = self.y2-self.y1+1
          lats_torun=[]
          lons_torun=[]
          vegfrac_torun=[]
          if (self.ne > 1 and size > 1 and size < self.nx*self.ny):
            all_ensembles_onejob = True
            k_max = 1
          else:
            all_ensembles_onejob = False
            k_max = self.ne
          for i in range(0,self.nx):
              for j in range(0,self.ny):
                vegfrac    = pct_natveg[self.y1+j,self.x1+i]
                bareground = pct_pft[0,self.y1+j,self.x1+i]
                if (bareground < 95.0 and vegfrac > 0.1 and landmask[self.y1+j,self.x1+i] > 0):
                  for k in range(0,k_max):
                    lons_torun.append(self.hdlongrid[self.y1+j,self.x1+i])
                    lats_torun.append(self.hdlatgrid[self.y1+j,self.x1+i])
                    if (pft < 0):
                      pftwt_torun[0, n_active] = sum(pct_pft[6:9,self.y1+j,self.x1+i])+pct_pft[3,self.y1+j,self.x1+i]
                      pftwt_torun[1, n_active] = sum(pct_pft[1:3,self.y1+j,self.x1+i])+pct_pft[4,self.y1+j,self.x1+i]+sum(pct_pft[9:12,self.y1+j,self.x1+i])
                      pftwt_torun[2, n_active] = sum(pct_pft[12:,self.y1+j,self.x1+i])
                    else:
                      pftwt_torun[pft, n_active] = 100.0
                    indx_torun.append(i)
                    indy_torun.append(j)
                    ens_torun.append(k)
                    vegfrac_torun.append((100.0-bareground)/100.0)
                    n_active = n_active+1

          #Load all forcing data into memory
          self.get_regional_forcings()
          #get forcings for one point to get relevant info
          self.load_forcings(lon=lons_torun[0], lat=lats_torun[0])
        else:
          #site forcing has already been loaded
          all_ensembles_onejob = False
          rank = 0
          size = 0
          n_active = self.ne
          if (n_active > 1 and use_MPI):
             from mpi4py import MPI
             comm=MPI.COMM_WORLD
             rank=comm.Get_rank()
             size=comm.Get_size()
          if (rank == 0):
            for k in range(0,self.ne):
               pftwt_torun[0:self.npfts,k] = self.pftfrac
               indx_torun.append(0)
               indy_torun.append(0)
               ens_torun.append(k)
            self.nx = 1
            self.ny = 1

        if (rank == 0):
          print('%d simulation units to run'%(n_active))
          n_done=0
          if (do_monthly_output):
             self.nt = (self.end_year-self.start_year+1)*12
             #istart=0
          else:
             self.nt = int(self.end_year-self.start_year+1)*365
             #istart=1

          model_output={}
          if (len(myoutvars) == 0):
            myoutvars = self.outvars
            for v in self.forcvars:
              if (v != 'time'):
                myoutvars.append(v)

          for v in myoutvars:
            if (v in self.forcvars):
              do_output_forcings = True
              model_output[v] = numpy.zeros([self.nt,self.ny,self.nx], numpy.float64)
            elif (v == 'ctcpools_vr'):
              model_output[v] = numpy.zeros([self.ne,16,self.nsoil_layers,self.nt,self.ny,self.nx], numpy.float64)
            elif (v == 'frootctam_pft'):
              model_output[v] = numpy.zeros([self.ne,self.npfts,self.nfroot_orders,self.nt,self.ny,self.nx], numpy.float64)
            elif (v == 'frootctam_pft_vr'):
              model_output[v] = numpy.zeros([self.ne,self.npfts,self.nfroot_orders,self.nsoil_layers,self.nt,self.ny,self.nx], numpy.float64)
            elif ('_vr' in v):
              model_output[v] = numpy.zeros([self.ne,self.nsoil_layers,self.nt,self.ny,self.nx], numpy.float64)
            elif ('_pft' in v):
              model_output[v] = numpy.zeros([self.ne,self.npfts,self.nt,self.ny,self.nx], numpy.float64)
            else:
              model_output[v] = numpy.zeros([self.ne,self.nt,self.ny,self.nx], numpy.float64) 
          self.pftfrac = numpy.zeros([self.ny,self.nx,self.npfts], numpy.float64)

          if (self.site == 'none'):
            self.load_forcings(lon=lons_torun[0], lat=lats_torun[0])

          if ((n_active == 1 and self.ne == 1) or size == 0):
            #No MPI
            for i in range(0,n_active):
                if (self.site == 'none'):
                  self.load_forcings(lon=lons_torun[i], lat=lats_torun[i])
                if (self.ne > 1):
                  for p in range(0,len(self.ensemble_pnames)):
                    self.parms[self.ensemble_pnames[p]][self.ensemble_ppfts[p]] = self.parm_ensemble[i,p]
                # run the model
                print('Starting SLEM instance')
                self.selm_instance(self.parms, use_nn=use_nn, spinup_cycles=spinup_cycles, seasonal_rootalloc=seasonal_rootalloc, \
                        pftwt=pftwt_torun[:,i]/100.0)
                self.pftfrac[indy_torun[i],indx_torun[i],:] = pftwt_torun[:,i]
                
                for v in myoutvars:
                  if (v in self.outvars and not (v in self.forcvars)):
                    if (do_monthly_output):
                      if (v != 'ctcpools_vr' and (not '_vr' in v) and (not '_pft' in v) ):
                        model_output[v][ens_torun[i],:,indy_torun[i],indx_torun[i]] = \
                         utils.daily_to_monthly(self.output[v][1:])
                      elif ('_vr' in v and not 'ctcpools' in v):
                          model_output[v][ens_torun[i],:,:,indy_torun[i],indx_torun[i]] = \
                           utils.daily_to_monthly(self.output[v][:,1:])
                      elif ('_pft' in v):
                          model_output[v][ens_torun[i],:,:,indy_torun[i],indx_torun[i]] = \
                           utils.daily_to_monthly(self.output[v][:,1:])
                    else:
                      # rewritten
                      if (('_vr' in v or '_pft' in v) and (not 'ctcpools' in v) and (not 'frootctam' in v)):
                        model_output[v][ens_torun[i],:,:,indy_torun[i],indx_torun[i]] = self.output[v][:,1:]
                      elif(v == 'frootctam_pft' or v == 'ctcpools_vr'):
                        model_output[v][ens_torun[i],:,:,:,indy_torun[i],indx_torun[i]] = self.output[v][:,:,1:]
                      elif(v == 'frootctam_pft_vr'):
                        model_output[v][ens_torun[i],:,:,:,:,indy_torun[i],indx_torun[i]] = self.output[v][:,:,:,1:]
                      else:
                        model_output[v][ens_torun[i],:,indy_torun[i],indx_torun[i]] = self.output[v][1:]
                  elif (v in self.forcvars):
                    if (do_monthly_output):
                       model_output[v][:,indy_torun[i],indx_torun[i]] = utils.daily_to_monthly(self.forcings[v])
                    else:
                       model_output[v][:,indy_torun[i],indx_torun[i]] = self.forcings[v][:]
            #test
            #print('frootctam shape',model_output['frootctam_pft'].shape)
            self.write_nc_output(model_output, do_monthly_output=do_monthly_output, prefix=prefix)
          else:
           #send first np-1 jobs where np is number of processes
           for n_job in range(1,size):
            comm.send(n_job, dest=n_job, tag=1)
            comm.send(0,     dest=n_job, tag=2)
            if (self.site == 'none'):
              self.load_forcings(lon=lons_torun[n_job-1], lat=lats_torun[n_job-1])
            parms = self.parms
            if (not all_ensembles_onejob and self.ne > 1):
              for p in range(0,len(self.ensemble_pnames)):
                #parms[self.ensemble_pnames[p]][self.ensemble_ppfts[p]] = self.parm_ensemble[ens_torun[n_job-1],p]
                parms[self.ensemble_pnames[p]][:] = self.parm_ensemble[ens_torun[n_job-1],p,:]

            comm.send(all_ensembles_onejob,  dest=n_job, tag=300)
            comm.send(do_output_forcings,    dest=n_job, tag=400)
            comm.send(self.forcings,         dest=n_job, tag=6)
            comm.send(self.start_year,       dest=n_job, tag=7)
            comm.send(self.end_year,         dest=n_job, tag=8)
            comm.send(self.nobs,             dest=n_job, tag=9)
            comm.send(self.lat,              dest=n_job, tag=10)
            comm.send(self.forcvars,         dest=n_job, tag=11)
            if (all_ensembles_onejob):
              comm.send(self.parm_ensemble,  dest=n_job, tag=100)
              comm.send(self.ensemble_pnames,dest=n_job, tag=101)
            else:
              comm.send(parms,               dest=n_job, tag=100)
            comm.send(myoutvars,             dest=n_job, tag=200)
            comm.send(pftwt_torun[:,n_job-1],dest=n_job, tag=500)

           #Assign rest of jobs on demand
           for n_job in range(size,n_active+1):
            process  = comm.recv(source=MPI.ANY_SOURCE, tag=3)
            thisjob  = comm.recv(source=process,        tag=4)
            myoutput = comm.recv(source=process,        tag=5)
            print('Received %d'%(thisjob))
            n_done = n_done+1

            comm.send(n_job, dest=process, tag=1)
            comm.send(0,     dest=process, tag=2)
            if (self.site == 'none'):
              self.load_forcings(lon=lons_torun[n_job-1], lat=lats_torun[n_job-1])
            if (not all_ensembles_onejob and self.ne > 1):
              for p in range(0,len(self.ensemble_pnames)):
                #parms[self.ensemble_pnames[p]][self.ensemble_ppfts[p]] = self.parm_ensemble[ens_torun[n_job-1],p]
                parms[self.ensemble_pnames[p]][:] = self.parm_ensemble[ens_torun[n_job-1],p,:]

            comm.send(all_ensembles_onejob,   dest=process, tag=300)
            comm.send(do_output_forcings,     dest=process, tag=400)
            comm.send(self.forcings,          dest=process, tag=6)
            comm.send(self.start_year,        dest=process, tag=7)
            comm.send(self.end_year,          dest=process, tag=8)
            comm.send(self.nobs,              dest=process, tag=9)
            comm.send(self.lat,               dest=process, tag=10)
            comm.send(self.forcvars,          dest=process, tag=11)
            if (all_ensembles_onejob):
              comm.send(self.parm_ensemble,   dest=process, tag=100)
              comm.send(self.ensemble_pnames, dest=process, tag=101)
            else:
              comm.send(parms,                dest=process, tag=100)
            comm.send(myoutvars,              dest=process, tag=200)
            comm.send(pftwt_torun[:,n_job-1], dest=process, tag=500)
            #write output
            for v in myoutvars:
              if (all_ensembles_onejob):
                for k in range(0,self.ne):
                  model_output[v][k,pfts_torun[thisjob-1],:,indy_torun[thisjob-1],indx_torun[thisjob-1]] = myoutput[v][k,:]
              elif((v in self.outvars) and (not v in self.forcvars)):
                # rewritten
                if (('_vr' in v or '_pft' in v) and (not 'ctcpools' in v) and (not 'frootctam' in v)):
                  model_output[v][ens_torun[thisjob-1],:,:,indy_torun[thisjob-1],indx_torun[thisjob-1]] = myoutput[v][0,:,:]
                elif(v == 'frootctam_pft' or v == 'ctcpools_vr'):
                  model_output[v][ens_torun[thisjob-1],:,:,:,indy_torun[thisjob-1],indx_torun[thisjob-1]] = myoutput[v][0,:,:,:]
                elif(v == 'frootctam_pft_vr'):
                  model_output[v][ens_torun[thisjob-1],:,:,:,:,indy_torun[thisjob-1],indx_torun[thisjob-1]] = myoutput[v][0,:,:,:,:]
                else:
                  model_output[v][ens_torun[thisjob-1],:,indy_torun[thisjob-1],indx_torun[thisjob-1]] = myoutput[v][0,:]                    
            self.pftfrac[indy_torun[thisjob-1],indx_torun[thisjob-1],:] = pftwt_torun[:,thisjob-1]

           #receive remaining messages and finalize
           while (n_done < n_active):
            process = comm.recv(source=MPI.ANY_SOURCE, tag=3)
            thisjob = comm.recv(source=process,        tag=4)
            myoutput= comm.recv(source=process,        tag=5)
            #vnum = 0
            print('Received %d'%(thisjob))
            n_done = n_done+1

            comm.send(-1, dest=process, tag=1)
            comm.send(-1, dest=process, tag=2)
            #write output
            for v in myoutvars:
              if (all_ensembles_onejob):
                for k in range(0,self.ne):
                  model_output[v][k,pfts_torun[thisjob-1],:,indy_torun[thisjob-1],indx_torun[thisjob-1]] = myoutput[v][k,:]
              elif((v in self.outvars) and (not v in self.forcvars)):
                # rewritten
                if (('_vr' in v or '_pft' in v) and (not 'ctcpools' in v) and (not 'frootctam' in v)):
                  model_output[v][ens_torun[thisjob-1],:,:,indy_torun[thisjob-1],indx_torun[thisjob-1]] = myoutput[v][0,:,:]
                elif(v == 'frootctam_pft' or v == 'ctcpools_vr'):
                  model_output[v][ens_torun[thisjob-1],:,:,:,indy_torun[thisjob-1],indx_torun[thisjob-1]] = myoutput[v][0,:,:,:]
                elif(v == 'frootctam_pft_vr'):
                  model_output[v][ens_torun[thisjob-1],:,:,:,:,indy_torun[thisjob-1],indx_torun[thisjob-1]] = myoutput[v][0,:,:,:,:]
                else:
                  model_output[v][ens_torun[thisjob-1],:,indy_torun[thisjob-1],indx_torun[thisjob-1]] = myoutput[v][0,:]
            self.pftfrac[indy_torun[thisjob-1],indx_torun[thisjob-1],:] = pftwt_torun[:,thisjob-1]
           # write to .nc
           self.write_nc_output(model_output, do_monthly_output=do_monthly_output, prefix=prefix)
           #MPI.Finalize()
        
        #Slave
        else:
          status=0
          while status == 0:
            myjob  = comm.recv(source=0, tag=1)
            status = comm.recv(source=0, tag=2)
            if (status == 0):
              all_ensembles_onejob   = comm.recv(source=0, tag=300)
              do_output_forcings     = comm.recv(source=0, tag=400)
              self.forcings          = comm.recv(source=0, tag=6)
              self.start_year        = comm.recv(source=0, tag=7)
              self.end_year          = comm.recv(source=0, tag=8)
              self.nobs              = comm.recv(source=0, tag=9)
              self.lat               = comm.recv(source=0, tag=10)
              self.forcvars          = comm.recv(source=0, tag=11)
              if (all_ensembles_onejob):
                self.parm_ensemble   = comm.recv(source=0, tag=100)
                self.ensemble_pnames = comm.recv(source=0, tag=101)
              else:
                myparms              = comm.recv(source=0, tag=100)
              myoutvars              = comm.recv(source=0, tag=200)
              mypftwt                = comm.recv(source=0, tag=500)
              
              #Initialize output arrays
              #self.output_ens = {}
              self.output    = {}
              thisoutput     = {}
              thisoutput_ens = {}
              for var in self.outvars:
                if (var == 'ctcpools_vr'):
                  self.output[var] = numpy.zeros([16,self.nsoil_layers,self.nobs+1], numpy.float64)
                elif (var == 'frootctam_pft'):
                  self.output[var] = numpy.zeros([self.npfts,self.nfroot_orders,self.nobs+1], numpy.float64)
                elif (var == 'frootctam_pft_vr'):
                  self.output[var] = numpy.zeros([self.npfts,self.nfroot_orders,self.nsoil_layers,self.nobs+1], numpy.float64)  
                elif ('_vr' in var):
                  self.output[var] = numpy.zeros([self.nsoil_layers,self.nobs+1], numpy.float64)
                elif ('_pft' in var):
                  self.output[var] = numpy.zeros([self.npfts,self.nobs+1], numpy.float64)
                else:
                  self.output[var] = numpy.zeros([self.nobs+1], numpy.float64)
              # loop over ensemble members
              if (all_ensembles_onejob):
                 k_max = self.ne
              else:
                 k_max = 1
              for k in range(0,k_max):
                # derive ensemble member parameter values
                if (all_ensembles_onejob):
                  myparms = self.pdefault
                  for p in range(0,len(self.ensemble_pnames)):
                    myparms[self.ensemble_pnames[p]] = self.parm_ensemble[k,p]
                # run the model
                print('Starting SLEM instance w/ MPI')
                self.selm_instance(myparms, use_nn=use_nn, spinup_cycles=spinup_cycles, seasonal_rootalloc=seasonal_rootalloc,pftwt=mypftwt/100.0)
                # deal with ensemble outputs
                for v in myoutvars:
                  # self.output --> thisoutput
                  if (v in self.outvars):
                    if (do_monthly_output):
                      if (('_vr' in v or '_pft' in v) and not 'ctcpools' in v):
                        thisoutput[v] = utils.daily_to_monthly(self.output[v][:,1:])
                      else:
                        thisoutput[v] = utils.daily_to_monthly(self.output[v][1:])
                    else:
                      #re-written
                      # 2D var
                      if (('_vr' in v or '_pft' in v) and (not 'ctcpools' in v) and (not 'frootctam' in v)):
                        thisoutput[v] = self.output[v][:,1:]
                      # 3D var
                      elif(v == 'frootctam_pft' or v == 'ctcpools_vr'):
                        thisoutput[v] = self.output[v][:,:,1:]
                      # 4D var
                      elif(v == 'frootctam_pft_vr'):
                        thisoutput[v] = self.output[v][:,:,:,1:]
                      # 1D var
                      else:
                        thisoutput[v] = self.output[v][1:]
                  elif (v in self.forcvars):
                    if (do_monthly_output):
                        thisoutput[v] = utils.daily_to_monthly(self.forcings[v])
                    else:
                        thisoutput[v] = self.forcings[v]
                  # thisoutput --> thisoutput_ens
                  if (k == 0):
                    if (('_vr' in v) and (not 'ctcpools' in v) and (not 'frootctam' in v)):
                      thisoutput_ens[v] = numpy.zeros([k_max,self.nsoil_layers,max(thisoutput[v].shape)], numpy.float64)
                    elif ('_pft' in v and (not 'frootctam' in v)):
                      thisoutput_ens[v] = numpy.zeros([k_max,self.npfts,       max(thisoutput[v].shape)], numpy.float64)
                    elif (v == 'frootctam_pft'):
                      thisoutput_ens[v] = numpy.zeros([k_max,self.npfts,self.nfroot_orders,max(thisoutput[v].shape)], numpy.float64)
                    elif (v == 'frootctam_pft_vr'):
                      thisoutput_ens[v] = numpy.zeros([k_max,self.npfts,self.nfroot_orders,self.nsoil_layers,max(thisoutput[v].shape)], numpy.float64)
                    elif (v == 'ctcpools_vr'):
                      thisoutput_ens[v] = numpy.zeros([k_max,16,self.nsoil_layers,max(thisoutput[v].shape)], numpy.float64)
                    else:
                      thisoutput_ens[v] = numpy.zeros([k_max, len(thisoutput[v])], numpy.float64)
                  # fill thisoutput_ens
                  if (('_vr' in v or '_pft' in v) and (not 'ctcpools' in v) and (not 'frootctam' in v)):
                    thisoutput_ens[v][k,:,:] = thisoutput[v]
                  elif (v == 'frootctam_pft' or v == 'ctcpools_vr'):
                    thisoutput_ens[v][k,:,:,:] = thisoutput[v]
                  elif (v == 'frootctam_pft_vr'):
                    thisoutput_ens[v][k,:,:,:,:] = thisoutput[v]
                  else:
                    thisoutput_ens[v][k,:] = thisoutput[v]

              comm.send(rank,           dest=0, tag=3)
              comm.send(myjob,          dest=0, tag=4)
              comm.send(thisoutput_ens, dest=0, tag=5)
          print('%d complete'%(rank))
          #MPI.Finalize()

    def write_nc_output(self, output, do_monthly_output=False,prefix='model'):
         #set up output file
         output_nc = Dataset(prefix+'_output.nc', 'w', format='NETCDF4')
         output_nc.createDimension('pft',   self.npfts)
         output_nc.createDimension('orders',self.nfroot_orders)
         output_nc.createDimension('soil',  self.nsoil_layers)
         output_nc.createDimension('lon',   self.nx)
         output_nc.createDimension('lat',   self.ny)
         if (self.ne > 1):
           output_nc.createDimension('ensemble',self.ne)
           #ens_out = output_nc.createVariable('ensemble','i4',('ensemble',))
           #ens_out.axis="E"
           #ens_out.CoordinateAxisType = "Ensemble"
          #  pnum=0
          #  for p in self.ensemble_pnames:
          #    #write parameter values to file
          #    pvars={}
          #    pvars[p] = output_nc.createVariable(p+'_pft'+str(self.ensemble_ppfts[pnum]), 'f8', ('ensemble',))
          #    pvars[p][:] = self.parm_ensemble[:,pnum]
          #    pnum=pnum+1
           pnum=0
           for p in self.ensemble_pnames:
             pvars={}
             pvars[p] = output_nc.createVariable(p, 'f8', ('ensemble','pft'))
             pvars[p][:,:] = self.parm_ensemble[:,pnum,:]
             pnum=pnum+1

         if (self.site == 'none'):
           lat_out = output_nc.createVariable('lat','f8',('lat',))
           lon_out = output_nc.createVariable('lon','f8',('lon',))
           lat_out[:] = self.hdlatgrid[self.y1:self.y2+1,self.x1]
           lon_out[:] = self.hdlongrid[self.y1,self.x1:self.x2+1]
         else:
           lat_out = self.latdeg
           lon_out = self.londeg
         pft_out = output_nc.createVariable('pft_frac','f4',('lat','lon','pft'))
         for n in range(0,self.ne):
           pft_out[:,:,:] = self.pftfrac[:,:,:]
         if (do_monthly_output):
            output_nc.createDimension('time',(self.end_year-self.start_year+1)*12)
            time = output_nc.createVariable('time','f8',('time',))
            dpm = [31,28,31,30,31,30,31,31,30,31,30,31]
            time[0] = 15.5
            mlast = 0
            for i in range(1,(self.end_year-self.start_year+1)*12):
              time[i] = time[i-1]+(dpm[mlast]+dpm[i % 12])/2.0
              mlast = i % 12
            #istart=0
         else:
            output_nc.createDimension('time',(self.end_year-self.start_year+1)*365)
            time = output_nc.createVariable('time','f8',('time',))
            for i in range(0,self.nobs):
              time[i] = i+0.5
            #istart=1
         time.units='Days since '+str(self.start_year)+'-01-01 00:00'

         ncvars={}
         for v in output:
            if (self.ne > 1):
              # if (not 'ctcpools' in v and not '_pft' in v and not '_vr' in v):
              #   #ncvars[v] = output_nc.createVariable(v, 'f4',('ensemble','pft','time','lat','lon'))
              #   #Default - don't output PFT-level output for ensembles
              #   ncvars[v] = output_nc.createVariable(v, 'f4',('ensemble','time','lat','lon'))
              #   ncvars[v][:,:,:,:] = output[v][:,:,:,:]
              # elif ('_vr' in v):
              #   ncvars[v] = output_nc.createVariable(v, 'f4',('ensemble','soil','time','lat','lon'))
              #   ncvars[v][:,:,:,:,:] = output[v][:,:,:,:,:] 
              # elif ('_pft' in v and v != 'frootctam_pft'):
              #   ncvars[v] = output_nc.createVariable(v, 'f4',('ensemble','pft','time','lat','lon'))
              #   ncvars[v][:,:,:,:,:] = output[v][:,:,:,:,:]
              # elif (v == 'frootctam_pft'):
              #   ncvars[v] = output_nc.createVariable(v, 'f4',('ensemble','pft','orders','time','lat','lon'))
              #   ncvars[v][:,:,:,:,:,:] = output[v][:,:,:,:,:,:]
              if (('_vr' in v) and (not 'ctcpools' in v) and (not 'frootctam' in v)):
                ncvars[v] = output_nc.createVariable(v, 'f4',('ensemble','soil','time','lat','lon'))
                ncvars[v][:,:,:,:,:] = output[v][:,:,:,:,:]
              elif ('_pft' in v and (not 'frootctam' in v)):
                ncvars[v] = output_nc.createVariable(v, 'f4',('ensemble','pft','time','lat','lon'))
                ncvars[v][:,:,:,:,:] = output[v][:,:,:,:,:]
              elif (v == 'frootctam_pft'):
                ncvars[v] = output_nc.createVariable(v, 'f4',('ensemble','pft','orders','time','lat','lon'))
                ncvars[v][:,:,:,:,:,:] = output[v][:,:,:,:,:,:]
              elif (v == 'frootctam_pft_vr'):
                ncvars[v] = output_nc.createVariable(v, 'f4',('ensemble','pft','orders','soil','time','lat','lon'))
                ncvars[v][:,:,:,:,:,:] = output[v][:,:,:,:,:,:,:]
              elif (v != 'ctcpools_vr' and (not v in self.forcvars)):
                ncvars[v] = output_nc.createVariable(v, 'f4',('ensemble','time','lat','lon'))
                ncvars[v][:,:,:,:] = output[v][:,:,:,:]
            else:
              if (('_vr' in v) and (not 'ctcpools' in v) and (not 'frootctam' in v)):
                ncvars[v] = output_nc.createVariable(v, 'f4',('soil','time','lat','lon'))
                ncvars[v][:,:,:,:] = output[v][0,:,:,:,:]
              elif ('_pft' in v and (not 'frootctam' in v)):
                ncvars[v] = output_nc.createVariable(v, 'f4',('pft','time','lat','lon'))
                ncvars[v][:,:,:,:] = output[v][0,:,:,:,:].squeeze()
              elif (v == 'frootctam_pft'):
                ncvars[v] = output_nc.createVariable(v, 'f4',('pft','orders','time','lat','lon'))
                ncvars[v][:,:,:,:,:] = output[v][0,:,:,:,:,:] #NOTE: .squeeze() removed for a bug
              elif (v == 'frootctam_pft_vr'):
                ncvars[v] = output_nc.createVariable(v, 'f4',('pft','orders','soil','time','lat','lon'))
                ncvars[v][:,:,:,:,:,:] = output[v][0,:,:,:,:,:,:]
              elif (v != 'ctcpools_vr'):
                ncvars[v] = output_nc.createVariable(v, 'f4',('time','lat','lon'))
                if (v in self.forcvars):
                    ncvars[v][:,:,:] = output[v][:,:,:]
                else:
                    ncvars[v][:,:,:] = output[v][0,:,:,:].squeeze()
         output_nc.close()

         #output for eden vis system - customize as needed
        #  if (self.ne > 1):
        #    eden_out = numpy.zeros([self.ne,pnum+1],numpy.float64)
        #    for n in range(0,self.ne):
        #      eden_out[n,0:pnum]      = self.parm_ensemble[n,:]
        #      eden_out[n,pnum:pnum+1] = numpy.mean(output['gpp'][n,0,0:60,0,0])*365.
        #    numpy.savetxt("foreden.csv",eden_out,delimiter=",")

    def generate_synthetic_obs(self, parms, err, use_nn=False):
        #generate synthetic observations from model with Gaussian error
        self.obs = numpy.zeros([self.nobs], numpy.float64)
        self.obs_err = numpy.zeros([self.nobs], numpy.float64)+err
        self.selm_instance(parms, use_nn=use_nn)
        for v in range(0,self.nobs):
            self.obs[v] = self.output[v]+numpy.random.normal(0,err,1)
        self.issynthetic = True
        self.actual_parms = parms

    def get_regional_forcings(self):
        print('Loading regional forcings')
        self.regional_forc={}
        fnames = ['TMAX','TMIN','FSDS','BTRAN']
        vnames = ['TSA', 'TSA', 'FSDS','BTRAN']
        fnum=0
        for f in fnames:
          os.system('mkdir -p '+oscm_dir+'/models/elm_drivers')
          driver_path = os.path.abspath(oscm_dir+'/models/elm_drivers')
          myfile = "GSWP3_fromELMSP_"+f+"_1980-2009.nc4"
          if (not os.path.exists(driver_path+'/'+myfile)):
            print('%s not found.  Downloading.'%(myfile))
            os.system('wget --no-check-certificate https://acme-webserver.ornl.gov/dmricciuto/elm_drivers/'+myfile)
            os.rename(myfile, driver_path+'/'+myfile)
          print('%s/%s'%(driver_path,myfile))
          myinput = Dataset(driver_path+'/'+myfile,'r')
          self.regional_forc[f.lower()] = myinput.variables[vnames[fnum]][:,:,:]
          myinput.close()
          fnum = fnum+1
        print ('Loading complete')

    def load_forcings(self, site='none', lat=-999, lon=-999):
      #Get single point data from E3SM style cpl_bypass input files
      #self.site=site
      self.forcvars = ['tmax','tmin','rad','cair','doy','dayl','btran','time']
      self.forcings = {}
      for fv in self.forcvars:
          self.forcings[fv] = []
      if (site != 'none' and site != 'US-MoT'):
        #Get data for requested site
        myinput = Dataset('./forcing_data/'+self.site+'_forcing.nc4','r',format='NETCDF4')
        npts  = myinput.variables['TBOT'].size              #number of half hours or hours
        tair  = myinput.variables['TBOT'][0,:]              #Air temperature (K)
        fsds  = myinput.variables['FSDS'][0,:]              #Solar radiation (W/m2)
        btran = fsds * 0.0 + 1.0
        self.latdeg = myinput.variables['LATIXY'][0]            #site latitude
        self.londeg = myinput.variables['LONGXY'][0]            #site longitude
        self.start_year = int(myinput.variables['start_year'][:]) #starting year of data
        self.end_year   = int(myinput.variables['end_year'][:])   #ending year of data
        self.npd = int(npts/(self.end_year - self.start_year + 1)/365)   #number of obs per day
        self.nobs = int((self.end_year - self.start_year + 1)*365)  #number of days
        self.lat = self.latdeg*numpy.pi/180.
        #populate hourly forcings (for NN)
        #self.forcings['tair_hourly'] = myinput.variables['TBOT'][0,:].copy()-273.15
        #self.forcings['fsds_hourly'] = myinput.variables['FSDS'][0,:].copy()
        #self.forcings['rh_hourly']   = myinput.variables['RH'][0,:].copy()
        #self.forcings['psrf_hourly'] = myinput.variables['PSRF'][0,:].copy()
        #self.forcings['wind_hourly'] = myinput.variables['WIND'][0,:].copy()
        myinput.close()
        #populate daily forcings
        for d in range(0,self.nobs):
          self.forcings['tmax'].append(max(tair[d*self.npd:(d+1)*self.npd])-273.15)
          self.forcings['tmin'].append(min(tair[d*self.npd:(d+1)*self.npd])-273.15)
          self.forcings['rad'].append(sum(fsds[d*self.npd:(d+1)*self.npd]*(86400/self.npd)/1e6))
          self.forcings['btran'].append(1.0)
          self.forcings['cair'].append(360)
          self.forcings['doy'].append((float(d % 365)+1))
          self.forcings['time'].append(self.start_year+d/365.0)
          #Calculate day length
          dec  = -23.4*numpy.cos((360.*(self.forcings['doy'][d]+10.)/365.)*numpy.pi/180.)*numpy.pi/180.
          mult = numpy.tan(self.lat)*numpy.tan(dec)
          if (mult >= 1.):
            self.forcings['dayl'].append(24.0)
          elif (mult <= -1.):
            self.forcings['dayl'].append(0.)
          else:
            self.forcings['dayl'].append(24.*numpy.arccos(-mult)/numpy.pi)
      elif (site == 'US-MoT'):
        # data from daymet
        myinput = Dataset('./forcing_data/'+self.site+'_forcing.nc4','r',format='NETCDF4')
        tmax = myinput.variables['tmax'][0,:]  #tmax
        tmin = myinput.variables['tmin'][0,:]  #tmin
        fsds = myinput.variables['FSDS'][0,:]  #Solar radiation (W/m2)
        btran = fsds * 0.0 + 1.0
        self.latdeg = myinput.variables['LATIXY'][0]              #site latitude
        self.londeg = myinput.variables['LONGXY'][0]              #site longitude
        self.start_year = int(myinput.variables['start_year'][:]) #starting year of data
        self.end_year   = int(myinput.variables['end_year'][:])   #ending year of data
        self.nobs       = int((self.end_year - self.start_year + 1)*365)  #number of days
        self.lat = self.latdeg*numpy.pi/180.
        myinput.close()
        #populate daily forcings
        for d in range(0,self.nobs):
          self.forcings['tmax'].append(tmax[d])
          self.forcings['tmin'].append(tmin[d])
          self.forcings['rad'].append(fsds[d]*86400/1e6)
          self.forcings['btran'].append(1.0)
          self.forcings['cair'].append(360)
          self.forcings['doy'].append((float(d % 365)+1))
          self.forcings['time'].append(self.start_year+d/365.0)
          #Calculate day length
          dec  = -23.4*numpy.cos((360.*(self.forcings['doy'][d]+10.)/365.)*numpy.pi/180.)*numpy.pi/180.
          mult = numpy.tan(self.lat)*numpy.tan(dec)
          if (mult >= 1.):
            self.forcings['dayl'].append(24.0)
          elif (mult <= -1.):
            self.forcings['dayl'].append(0.)
          else:
            self.forcings['dayl'].append(24.*numpy.arccos(-mult)/numpy.pi)
      elif (lat >= -90 and lon >= -180):
        #Get closest gridcell from reanalysis data
        self.latdeg=lat
        if (lon > 180):
            lon=lon-360.
        if (lat > 9.5 and lat < 79.5 and lon > -170.5 and lon < -45.5):
          xg = int(round((lon + 170.25)*2))
          yg = int(round((lat - 9.75)*2))
          tmax = self.regional_forc['tmax'][:,yg,xg]
          tmin = self.regional_forc['tmin'][:,yg,xg]
          btran = self.regional_forc['btran'][:,yg,xg]
          fsds = self.regional_forc['fsds'][:,yg,xg]
        else:
          print('regions outside North America not currently supported')
          sys.exit(1)
        self.start_year = 1980
        self.end_year   = 2009
        self.npd = 1
        self.nobs = (self.end_year - self.start_year + 1)*365
        self.lat = self.latdeg*numpy.pi/180.

        #populate daily forcings
        self.forcings['tmax']  = tmax-273.15
        self.forcings['tmin']  = tmin-273.15
        self.forcings['btran'] = btran
        self.forcings['rad']   = fsds*86400/1e6
        self.forcings['cair']  = numpy.zeros([self.nobs], numpy.float64) + 360.0
        self.forcings['doy']   = (numpy.cumsum(numpy.ones([self.nobs], numpy.float64)) - 1) % 365 + 1
        self.forcings['time']  = self.start_year + (numpy.cumsum(numpy.ones([self.nobs], numpy.float64)-1))/365.0
        self.forcings['dayl']  = numpy.zeros([self.nobs], numpy.float64)
        for d in range(0,self.nobs):
          #Calculate day length
          dec  = -23.4*numpy.cos((360.*(self.forcings['doy'][d]+10.)/365.)*numpy.pi/180.)*numpy.pi/180.
          mult = numpy.tan(self.lat)*numpy.tan(dec)
          if (mult >= 1.):
            self.forcings['dayl'][d] = 24.0
          elif (mult <= -1.):
            self.forcings['dayl'][d] = 0.
          else:
            self.forcings['dayl'][d] = 24.*numpy.arccos(-mult)/numpy.pi

      #define the x axis for plotting output (time, or one of the inputs)
      self.xlabel = 'Time (years)'
      #Initialize output arrays
      self.output = {}
      for var in self.outvars:
        if (var == 'ctcpools_vr'):
          self.output[var] = numpy.zeros([16,self.nsoil_layers,self.nobs+1], numpy.float64)
        elif ('_pft' in var and '_vr' in var):
          self.output[var] = numpy.zeros([self.npfts,self.nfroot_orders,self.nsoil_layers,self.nobs+1], numpy.float64)
        elif ('_vr' in var):
          self.output[var] = numpy.zeros([self.nsoil_layers,self.nobs+1], numpy.float64)
        elif ('_pft' in var and var != 'frootctam_pft'):
          self.output[var] = numpy.zeros([self.npfts,self.nobs+1], numpy.float64)
        elif (var == 'frootctam_pft'):
          self.output[var] = numpy.zeros([self.npfts,self.nfroot_orders,self.nobs+1], numpy.float64)
        else:
          self.output[var] = numpy.zeros([self.nobs+1], numpy.float64)

    def generate_ensemble(self, n_ensemble, pnames, ppfts, fname='', normalized=False):
      """
      Generate parameters' values for ensemble runs.
      
      Load actual observations and uncertainties
      
      Parameters:
        n_ensemble: integer;size of ensemble
        pnames:     list of parameter names participating ensemble runs
        ppfts:      list of pfts to participate ensemble runs
        fname:

      Return:
      """

      self.ensemble_pnames = pnames
      self.ensemble_ppfts  = ppfts # self.npfts
      self.ne              = n_ensemble
      #self.parm_ensemble   = numpy.zeros([n_ensemble,len(pnames)])
      # 2d-->3d?
      self.parm_ensemble   = numpy.zeros([n_ensemble,len(pnames),self.npfts])
      
      if (fname != ''):
        #print('Generating parameter ensemble from %d'%(fname))
        inparms = open(fname,'r')
        lnum = 0
        for s in inparms:
          pvals = s.split()
          if (lnum < n_ensemble):
            for p in range(0,len(pnames)):
              if (normalized):
                self.parm_ensemble[lnum,p] = self.pmin[pnames[p]][ppfts[p]]+0.5* \
                     (float(pvals[p]))*(self.pmax[pnames[p]][ppfts[p]]-self.pmin[pnames[p]][ppfts[p]])
              else:
                self.parm_ensemble[lnum,p] = float(pvals[p])
          lnum=lnum+1
        inparms.close()
      else:
        # HACK: to have identical ensemble members uncomment line below
        numpy.random.seed(2018)
        for n in range(0,n_ensemble):          
          for p in range(0,len(pnames)):
            #Sample uniformly from the parameter space
            #NOTE:Samples are uniformly distributed over the half-open interval [low, high) (includes low, but excludes high).
            #self.parm_ensemble[n,p] = numpy.random.uniform(low=self.pmin[pnames[p]][ppfts[p]],high=self.pmax[pnames[p]][ppfts[p]])
            # draw values of the size of # PFTs
            self.parm_ensemble[n,p,:] = numpy.random.uniform(low=self.pmin[pnames[p]][:],high=self.pmax[pnames[p]][:])
        #numpy.savetxt('inputs.txt', self.parm_ensemble)
