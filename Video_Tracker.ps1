#Get-Process vrmonitor | select starttime
#PROGRAM ARGUMENTS
#param($name)
$name = $args[0]
$Student_Name = $args[1]
$ID = $args[2]

$Quit = $false
#Write-Output $name
#Gather user information
#do {
#    $Student_Name = Read-Host "Please enter your name"
#    [int]$ID = Read-Host "Please enter your Student ID"
#    #Write-Output "$ID"
#} while ($Quit -eq $false -and !($ID -and ($Student_Name -ne "")))

#List all videos available to watch
$File_Path = "..\..\..\360 Videos\" + $name

$Files = Get-ChildItem -Path '..\..\..\360 Videos' -Name
$i = 0
foreach ($Vid in $Files) {
#    Write-Output "$i. $File"
    if ($Vid -eq $name) {
        $Video_num = $i
    }
    $i++
}

#Ask user what video they would like to watch
#$Valid_Selection = $false
#do {
#    [int]$Video = Read-Host "Please select what video to play. Enter a number 1-$($i-1)"
#    if ($Video -gt 0 -and $Video -lt $i) {
#        $Valid_Selection = $true
#    }
#} while (!$Valid_Selection)

#Launch the video in steamvr
#$File_Path = "C:\Users\svfr_\OneDrive\Documents\360 Videos\" + $Files[$($Video-1)]
#Write-Output "$File_Path"
$Time_Watched = Measure-Command {
    Start-Process -FilePath $File_Path -Wait
}
$Time_Watched = $Time_Watched.TotalMinutes
#$Time_Watched = 25

#Check if the user has watched the full video
$Shell = New-Object -COMObject Shell.Application
#$Folder = Split-Path -Parent $File_Path
#$Folder = Split-Path $File_Path
$Folder = Split-Path (Resolve-Path -Path $File_Path)
$Folder = $Folder + '\'
#Write-Output $Folder
$File = Split-Path $File_Path -Leaf
#Write-Output $File
$Shell_Folder = $Shell.Namespace($Folder)
#$Shell_Folder = $Shell.Namespace((Resolve-Path -Path $File_Path))
#Write-Output $Shell_Folder.Title
$Shell_File = $Shell_Folder.ParseName($File)
$Video_Length = [timespan]::Parse($Shell_Folder.GetDetailsOf($Shell_File, 27)).TotalMinutes


if ($Time_Watched -ge ($Video_Length * 0.9)) {
    #If the user has watched the full video, log it to the csv file
    #$Csv = Import-Csv "..\powershell_test_output.csv"
    #$Student_Exists = $false
    #Write-Output $row.'STUDENT NAME'
    #Write-Output $Student_Name
    #$File_Name = $Files[$($Video-1)] -replace '\..*'
    #$File_Name = $Files[$($Video-1)].Substring(0, $($Files[$($Video-1)].Length) - 4)
    #$File_Name = $Files[$name].Substring(0, $($Files[$name].Length) - 4)
    #$File_Name = $name.Substring(0, $name.Length-4)
    #Write-Output $File_Name

    #If student already exists in the file, log the video they watched as '1' for completed
    #foreach($row in $Csv) {
    #    if ($row.'STUDENT ID' -eq $ID) {
    #        $Student_Exists = $true
    #        $row.$($File_Name) = 1
    #        #Write-Output $row
    #    }
    #}
    #If the student does not exist yet, add their entry into the CSV file
    #if (!$Student_Exists) {
    #    $New_Row = $Csv[1]
    #    #Create a clone of the header row and set each column to a value of '0'
    #    foreach ($col in $Csv[1].PSObject.Properties) {
    #        #Add-Content C:\Users\svfr_\OneDrive\Documents\powershell_test_output.csv "$Student_Name, $ID"
    #        $New_Row.$($col.Name) = 0
    #    }
    #    $New_Row.'STUDENT NAME' = $Student_Name
    #    $New_Row.'STUDENT ID' = $ID
    #    $New_Row.$($File_Name) = 1
    #    #Write-Output $New_Row
    #    $New_Row | Export-csv -path "..\powershell_test_output.csv" -Append
    #}
    #Else {
    #    $Csv | Export-csv -Path "..\powershell_test_output.csv" -NoTypeInformation
    #}
    
    #$EncryptionKeyData = Get-Content "C:\Users\svfr_\OneDrive\Documents\360 Videos\360 Videos Tracking Program\Encryption.key"
    #ALL THE ENCRYPTION STUFF
    #$EncryptionKeyData = Get-Content "..\Encryption.key"
    #$Password = ConvertTo-SecureString $ID -AsPlainText -Force
    #THE ENCRYPTED ID
    #$EP = ConvertFrom-SecureString $Password -Key $EncryptionKeyData

    $headers = New-Object "System.Collections.Generic.Dictionary[[String],[String]]"
    $headers.Add("Content-Type", "application/json")

    $body = @"
    {
    `"id`": `"$ID`",
    `"videoNumber`": `"$video_num`",
    `"status`": `"1`"
    }
"@

    $response = Invoke-RestMethod 'http://150.136.241.0:5000/uploadVideoResults' -Method 'POST' -Headers $headers -Body $body
    $response | ConvertTo-Json
}



#Read-Host -Prompt "Press Enter to exit"
#Remove all variables at the end of the process
#Remove-Variable Quit
#Remove-Variable Student_Name
#Remove-Variable ID
#Remove-Variable i
#Remove-Variable Video
#Remove-Variable Valid_Selection
#Remove-Variable Files
#Remove-Variable File
#Remove-Variable File_Path
#Remove-Variable Shell
#Remove-Variable Folder
#Remove-Variable Shell_Folder
#Remove-Variable Shell_File
#Remove-Variable Video_Length
#Remove-Variable Time_Watched
#Remove-Variable Csv
#Remove-Variable Student_Exists
#Remove-Variable row
#Remove-Variable File_Name
#Remove-Variable New_Row