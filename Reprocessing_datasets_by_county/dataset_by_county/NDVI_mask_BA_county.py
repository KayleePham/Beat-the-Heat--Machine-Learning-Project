# NOTES: this file runs smoothly on my machine (no errors and no output)
#   if it doesn't run on yours, it might be because of the dir setup (see below)

# Directory setup notes: in the same dir as this .py file, there should be
# the PreprocessingAuxiliaryFunctions.py, and 2 data folders: 
# input_data_files (all the NDVI images) and burn_area_files. Within the burn_are_files
# there should be 2 essential folders, burn_date and QA. If all is correct, you shouldn't
# need to reconfigure anything because of the function that uses relative paths 
# (af.create_abs_path_from_relative('rel_path')). If you have questions or want to verify the setup
# Please send me a message on discord

import fiona
import rasterio
import rasterio.mask
import matplotlib.pyplot as plt
import pandas as pd
import geopandas as gpd
import os   
import sys
import glob
from osgeo import gdal
import numpy as np
import scipy.ndimage
import datetime as dt

from PreprocessingAuxiliaryFunctions import PreprocessingAuxiliaryFunctions as auxFuncts

def main():
    af = auxFuncts()

    CA_counties_geodf = af.read_geojson_geodf()
    shapes = af.extract_shapes_from_county_geometry(CA_counties_geodf)
    #* note: if the shape file doesn't work, uncomment the line below (starting with "shapes = ...") this to fix
    # print(CA_counties_geodf)
    # print(shapes)
    # shapes = af.read_geojson()  # read in list of county boundaries


    # Setting up input directories
    out_dir = af.create_abs_path_from_relative('output')
    BAinDir = af.create_abs_path_from_relative('burn_area_files\\burn_date')  # i think this is being used for BA and QA
    NDVI_inDir = af.create_abs_path_from_relative('input_data_files')
    BA_burn_date_dir = af.create_abs_path_from_relative('burn_area_files\\burn_date')
    BA_QA_dir = af.create_abs_path_from_relative('burn_area_files\\QA')

    out_dir = os.path.normpath(os.path.split(BAinDir)[0] + os.sep + 'output') + '\\'  # Create and set output directory
    if not os.path.exists(out_dir): os.makedirs(out_dir)
    
    # NDVI_inDir = (r'C:\Users\Student\Documents\School\Senior design\dataset_by_county\input_data_files')  #Path to NDVI files
    #* note: dir setup for files should be as follows:
    #* \GitHub\Beat-the-Heat--Machine-Learning\Reprocessing_datasets_by_county\dataset_by_county\NDVI_by_county.py
    #* within the 'dataset_by_county' folder, also include the NDVI dataset in a folder named 'input_data_files'
    home_dir = os.getcwd()
    os.chdir(NDVI_inDir)                                                            # Change to working directory
    EVIFiles        = glob.glob('MOD13A1.006__500m_16_days_NDVI_**.tif')            # Search for and create a list of EVI files
    EVIqualityFiles = glob.glob('MOD13A1.006__500m_16_days_VI_Quality**.tif')       # Search the directory for the associated quality .tifs
    EVIlut          = glob.glob('MOD13A1-006-500m-16-days-VI-Quality-lookup.csv')   # Search for look up table 
    EVI_v6_QA_lut   = pd.read_csv(EVIlut[0])   
    EVIgoodQuality = af.extracting_good_quality_vals_from_NDVI_lut(EVI_v6_QA_lut)   # print(EVIqualityFiles)  # debugging output

    ###### Burn Area Files
    os.chdir(BA_burn_date_dir)                                                      # Change to working directory
    BAFiles         = glob.glob('MCD64A1.006_Burn_Date_**.tif')                     # Search for and create a list of BA files
    os.chdir(BA_QA_dir) 
    BAqualityFiles  = glob.glob('MCD64A1.006_QA_**.tif')                            # Search the directory for the associated quality .tifs
    os.chdir(NDVI_inDir)                                                            # LUTs are in NDVI folder
    BAlut           = glob.glob('MCD64A1-006-QA-lookup.csv')                        # Search for BA look up table 
    v6_BAQA_lut     = pd.read_csv(BAlut[0])                                           # Read in the lut
    BAgoodQuality   = af.extracting_good_quality_vals_from_BA_lut(v6_BAQA_lut)      # Retrieve list of possible QA values from the quality dataframe
    BAVal = tuple(range(1, 367, 1))                                                 # List of numbers between 1-366. Used when masking by BA 
    
    ## Initialize Dataframe for final results
    NDVI_result = []

    # Traverse through the list of NDVI files 
    for i in range(0, len(EVIFiles)):
        os.chdir(NDVI_inDir)
        EVI         = gdal.Open(EVIFiles[i])                                        # Read file in, starting with MOD13Q1 version 6 #* in dir input_files
        EVIquality  = gdal.Open(EVIqualityFiles[i])                                 # Open the first quality file

        EVIdate     = af.getEVI_Date_Year_Month(EVIFiles[i], "D")                   # Get the Date of the file in format MM/DD/YYYY
        EVI_year    = af.getEVI_Date_Year_Month(EVIFiles[i], "Y")                   # Get the year of the file 
        EVI_month   = af.getEVI_Date_Year_Month(EVIFiles[i], "M")                   # Get the month of the file
        BAFileName  = af.getBAFileName(BAFiles, EVI_month, EVI_year)                # Get BA filename for the current NDVI file
        BAQAFileName= af.getBAFileName(BAqualityFiles, EVI_month, EVI_year)         # Get BA QA filename for the current NDVI file
        for county_masked in shapes:

            af.maskByShapefileAndStore(EVIFiles[i],EVIqualityFiles[i], BAFileName, BAQAFileName, county_masked)
            os.chdir(out_dir) 
            ###--------------------------------------------------------------------------###
            ###    OPEN ALL 4 temporary files created get Quality data and mask by BA    ###
            ###--------------------------------------------------------------------------###
            ##--------------------------------------------------------------------------
            EVI         = gdal.Open(af.EVI_temp)                                    # Read EVI temporary file for current county in the loop
            EVIBand     = EVI.GetRasterBand(1)                                      # Read the band (layer)
            EVIData     = EVIBand.ReadAsArray().astype('float')                     # Import band as an array with type float
            ##--------------------------------------------------------------------------
            EVIquality  = gdal.Open(af.EVIQA_temp)                                  # Open temporary EVI quality file
            EVIqualityData = EVIquality.GetRasterBand(1).ReadAsArray()              # Read in as an array
            EVIquality = None 
            ##--------------------------------------------------------------------------
            BA          = gdal.Open(af.BA_temp)                                     # Read BA temporary file for current county in the loop
            BABand      = BA.GetRasterBand(1)                                       # Read the band (layer)
            BAData      = BABand.ReadAsArray().astype('float')                      # Import band as an array with type float
            ##--------------------------------------------------------------------------
            BAquality   = gdal.Open(af.BAQA_temp)                                   # Open temporary BA quality file
            BAqualityData = BAquality.GetRasterBand(1).ReadAsArray()                # Read in as an array
            BAquality = None 
            #--------------------------------------------------------------------------
            # File Metadata
            BA_meta = BA.GetMetadata()                        # Store metadata in dictionary
            EVI_meta = EVI.GetMetadata()                      # Store metadata in dictionary

            # Band metadata
            BAFill = BABand.GetNoDataValue()                  # Returns fill value
            BA = None                                         # Close the GeoTIFF file

            # Band metadata
            EVIFill = EVIBand.GetNoDataValue()                # Returns fill value
            EVI = None                                        # Close the GeoTIFF file

            BAscaleFactor = float(BA_meta['scale_factor'])    # Search the metadata dictionary for the scale factor 
            BAData[BAData == BAFill] = np.nan                 # Set the fill value equal to NaN for the array
            BAScaled = BAData * BAscaleFactor                 # Apply the scale factor using simple multiplication

            EVIscaleFactor = float(EVI_meta['scale_factor'])  # Search the metadata dictionary for the scale factor 
            EVIData[EVIData == EVIFill] = np.nan              # Set the fill value equal to NaN for the array
            EVIScaled = EVIData * EVIscaleFactor              # Apply the scale factor using simple multiplication

            #----- MASK AND GET MEAN VALUE -----#
            BA_masked   = np.ma.MaskedArray(BAScaled, np.in1d(BAqualityData, BAgoodQuality, invert = True))         # Apply QA mask to the BA data
            EVI_masked  = np.ma.MaskedArray(EVIScaled, np.in1d(EVIqualityData, EVIgoodQuality, invert = True))      # Apply QA mask to the EVI data
            EVI_BA      = np.ma.MaskedArray(EVI_masked, np.in1d(BA_masked, BAVal, invert = True))                   # Mask array, include only BurnArea
            EVI_mean    = np.mean(EVI_BA.compressed())                                                              # Get EVI mean value of the Burn Area
            
            #----- STORE IT IN RESULT DATAFRAME -----#
            NDVI_result.append([EVIdate,EVI_mean])      
    
    # add header to output dataframe
    result_df = pd.DataFrame(NDVI_result, columns=["Date","NDVI"])
    result_df['Date'] = pd.to_datetime(result_df['Date'], format='%m/%d/%Y')
    result_df = result_df.set_index('Date')
    result_series = result_df.resample('D').mean()

    result_series["NDVI"] = result_series["NDVI"].interpolate(method='linear')
    os.chdir(out_dir)
    result_series.to_csv('NDVI2019_2020.csv', index = True)  # Export statistics to CSV
    print(result_series)  


if __name__ == "__main__":
    # execute only if run as a script
    main()